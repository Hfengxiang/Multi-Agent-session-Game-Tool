import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

from adapters.base import AgentResult
from core.control_queue import ControlQueue
from core.mailbox import Mailbox
from core.game_master import GameMaster
from adapters.claude_code import ClaudeCodeAdapter


class FakeAdapter(ClaudeCodeAdapter):
    """Adapter that returns canned responses instead of calling claude CLI."""

    def __init__(self, work_dir, executor_outputs, evaluator_outputs):
        super().__init__(work_dir)
        self.executor_outputs = executor_outputs
        self.evaluator_outputs = evaluator_outputs
        self.exec_call_count = 0
        self.eval_call_count = 0

    def execute(self, prompt, allowed_tools, timeout):
        # Determine if this is executor or evaluator by checking tools
        if "Write" in allowed_tools:
            output = self.executor_outputs[self.exec_call_count % len(self.executor_outputs)]
            self.exec_call_count += 1
        else:
            output = self.evaluator_outputs[self.eval_call_count % len(self.evaluator_outputs)]
            self.eval_call_count += 1
        return AgentResult(success=True, stdout=output, stderr="", exit_code=0)


def test_game_master_reaches_threshold():
    with tempfile.TemporaryDirectory() as tmp:
        work_dir = Path(tmp) / ".game-master" / "test-001"
        work_dir.mkdir(parents=True)

        # Create dummy target file
        target = Path(tmp) / "test.py"
        target.write_text("# hello")

        # Create prompts dir
        prompts_dir = Path(tmp) / "prompts"
        prompts_dir.mkdir()
        (prompts_dir / "executor-base.md").write_text("executor base")
        (prompts_dir / "evaluator-base.md").write_text("evaluator base")

        # Create role files
        (Path(tmp) / "exec-role.md").write_text("exec role")
        (Path(tmp) / "eval-role.md").write_text("eval role")

        executor_outputs = [
            "---EXECUTOR SUMMARY---\nSUMMARY: made it better\nFILES: test.py\nCHANGES: refactored\n---END---",
            "---EXECUTOR SUMMARY---\nSUMMARY: fixed remaining issues\nFILES: test.py\nCHANGES: added docs\n---END---",
        ]
        evaluator_outputs = [
            "---EVALUATOR SCORE---\nSCORE: 85\nFEEDBACK: almost there\nSTRENGTHS:\n- good start\nWEAKNESSES:\n- needs docs\nSUGGESTIONS:\n- add docs\n---END---",
            "---EVALUATOR SCORE---\nSCORE: 96\nFEEDBACK: excellent\nSTRENGTHS:\n- clean code\nWEAKNESSES:\n\nSUGGESTIONS:\n\n---END---",
        ]

        adapter = FakeAdapter(work_dir, executor_outputs, evaluator_outputs)

        # Build GameMaster manually (bypass __init__ to avoid real prompts dir path)
        gm = GameMaster.__new__(GameMaster)
        gm.task = "improve test.py"
        gm.target = str(target)
        gm.adapter = adapter
        gm.work_dir = work_dir
        gm.max_rounds = 10
        gm.timeout = 300
        gm.score_threshold = 95
        gm.mailbox = Mailbox(work_dir)
        gm.control_queue = ControlQueue(work_dir)
        gm.executor_base = "executor base"
        gm.evaluator_base = "evaluator base"
        gm.executor_role = "exec role"
        gm.evaluator_role = "eval role"
        gm._aborted = False
        gm._best_score = 0

        import signal
        gm._handle_sigint = lambda *a: None

        gm.EXECUTOR_TOOLS = ["Read", "Write", "Edit", "Glob", "Grep", "Bash"]
        gm.EVALUATOR_TOOLS = ["Read", "Glob", "Grep", "Bash"]

        gm._run_with_retry = lambda prompt, tools: adapter.execute(prompt, tools, 300)

        result = gm.run()

        assert result["status"] == "completed"
        assert result["best_score"] == 96
        assert result["rounds"] == 2


def test_control_queue_quit():
    with tempfile.TemporaryDirectory() as tmp:
        work_dir = Path(tmp) / ".game-master" / "test-002"
        work_dir.mkdir(parents=True)

        cq = ControlQueue(work_dir)
        cq.push("quit")
        commands = cq.pop_all()
        assert cq.has_quit(commands)
        # Queue should be cleared after pop
        assert cq.pop_all() == []


def test_mailbox_roundtrip():
    with tempfile.TemporaryDirectory() as tmp:
        work_dir = Path(tmp) / ".game-master" / "test-003"
        work_dir.mkdir(parents=True)

        mb = Mailbox(work_dir)
        mb.put_executor_msg({"score": 85, "feedback": "ok"})
        msg = mb.get_executor_msg()
        assert msg["score"] == 85

        mb.put_evaluator_msg({"summary": "changed things", "files_modified": ["a.py"]})
        msg = mb.get_evaluator_msg()
        assert msg["summary"] == "changed things"

        mb.append_history({"round": 1, "score": 85})
        mb.append_history({"round": 2, "score": 96})
        history = mb.read_history()
        assert len(history) == 2
