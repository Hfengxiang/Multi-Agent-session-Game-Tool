import signal
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from core.control_queue import ControlQueue
from core.mailbox import Mailbox
from adapters.base import AgentAdapter, AgentResult


class GameMaster:
    """Orchestrates the executor-evaluator adversarial game loop."""

    EXECUTOR_TOOLS = ["Read", "Write", "Edit", "Glob", "Grep", "Bash"]
    EVALUATOR_TOOLS = ["Read", "Glob", "Grep", "Bash"]

    def __init__(
        self,
        task: str,
        target: str,
        executor_role_path: Path,
        evaluator_role_path: Path,
        adapter: AgentAdapter,
        work_dir: Path,
        max_rounds: int = 10,
        timeout: int = 300,
        score_threshold: int = 95,
    ):
        self.task = task
        self.target = target
        self.adapter = adapter
        self.work_dir = work_dir
        self.max_rounds = max_rounds
        self.timeout = timeout
        self.score_threshold = score_threshold

        self.mailbox = Mailbox(work_dir)
        self.control_queue = ControlQueue(work_dir)

        self.executor_base = (Path(__file__).parent.parent / "prompts" / "executor-base.md").read_text(encoding="utf-8")
        self.evaluator_base = (Path(__file__).parent.parent / "prompts" / "evaluator-base.md").read_text(encoding="utf-8")
        self.executor_role = executor_role_path.read_text(encoding="utf-8")
        self.evaluator_role = evaluator_role_path.read_text(encoding="utf-8")

        self._aborted = False
        self._best_score = 0
        signal.signal(signal.SIGINT, self._handle_sigint)

    def _handle_sigint(self, signum, frame):
        self._aborted = True
        print("\n[GameMaster] Interrupted by user. Finishing current round...")

    def run(self) -> dict:
        print(f"[GameMaster] Starting game for task: {self.task}")
        print(f"[GameMaster] Target: {self.target}")
        print(f"[GameMaster] Max rounds: {self.max_rounds}, Score threshold: {self.score_threshold}")
        print()

        for round_num in range(1, self.max_rounds + 1):
            # --- Check control queue ---
            commands = self.control_queue.pop_all()
            if self.control_queue.has_quit(commands):
                print("[GameMaster] Quit command received. Stopping.")
                return self._finish("aborted")

            if self._aborted:
                return self._finish("aborted")

            # --- Executor turn ---
            feedback = self.mailbox.get_executor_msg()
            history = self.mailbox.read_history()

            exec_prompt = self.adapter.build_prompt(
                base_prompt=self.executor_base,
                role=self.executor_role,
                task=f"Target: {self.target}\n\nTask: {self.task}",
                feedback=feedback,
                history=history,
            )
            exec_result = self._run_with_retry(exec_prompt, self.EXECUTOR_TOOLS)
            if exec_result is None:
                return self._finish("error")

            exec_parsed = self.adapter.parse_output(exec_result.stdout)
            exec_parsed["round"] = round_num
            exec_parsed["from"] = "executor"
            self.mailbox.put_evaluator_msg(exec_parsed)

            # --- Evaluator turn ---
            exec_msg = self.mailbox.get_evaluator_msg()
            eval_prompt = self.adapter.build_prompt(
                base_prompt=self.evaluator_base,
                role=self.evaluator_role,
                task=f"Target: {self.target}\n\nTask: {self.task}",
                feedback=exec_msg,
                history=history,
            )
            eval_result = self._run_with_retry(eval_prompt, self.EVALUATOR_TOOLS)
            if eval_result is None:
                return self._finish("error")

            eval_parsed = self.adapter.parse_output(eval_result.stdout)
            eval_parsed["round"] = round_num
            eval_parsed["from"] = "evaluator"
            self.mailbox.put_executor_msg(eval_parsed)

            # --- Record & print ---
            round_entry = {
                "round": round_num,
                "executor": exec_parsed.get("summary", exec_parsed.get("changes", "")),
                "evaluator_score": eval_parsed.get("score", 0),
                "evaluator_feedback": eval_parsed.get("feedback", ""),
            }
            self.mailbox.append_history(round_entry)

            score = eval_parsed.get("score", 0)
            self._best_score = max(self._best_score, score)

            print(
                f"[Round {round_num}] "
                f"Executor: {exec_parsed.get('summary', '...')[:80]} "
                f"→ Evaluator: {score}分 | {eval_parsed.get('feedback', '')[:80]}"
            )

            if score >= self.score_threshold:
                print(f"\n[GameMaster] Target score reached! ({score} >= {self.score_threshold})")
                return self._finish("completed")

            time.sleep(1)  # brief cooldown between rounds

        print(f"\n[GameMaster] Max rounds reached. Best score: {self._best_score}")
        return self._finish("max_rounds")

    def _run_with_retry(self, prompt: str, tools: list[str]) -> AgentResult | None:
        for attempt in (1, 2):
            result = self.adapter.execute(prompt, tools, self.timeout)
            if result.success:
                return result
            if "timed out" in result.stderr.lower():
                print(f"  [GameMaster] Agent timed out (attempt {attempt}/2), retrying...")
                continue
            print(f"  [GameMaster] Agent error (attempt {attempt}/2): {result.stderr[:200]}")
            if attempt < 2:
                continue
        print(f"  [GameMaster] Agent failed after 2 attempts. Stopping.")
        return None

    def _finish(self, status: str) -> dict:
        history = self.mailbox.read_history()
        return {
            "status": status,
            "rounds": len(history),
            "best_score": self._best_score,
            "history": history,
            "work_dir": str(self.work_dir),
        }
