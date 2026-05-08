# Game Master Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python CLI that orchestrates two Claude Code sessions in an adversarial game loop — executor modifies files, evaluator scores and gives feedback, iterating until score ≥ 95.

**Architecture:** Adapter pattern isolates CLI backends. GameMaster runs the state machine loop, delegating AI calls to AgentAdapter. ControlQueue provides out-of-band interrupt. Mailbox passes structured messages between agents. All I/O is file-based for auditability.

**Tech Stack:** Python 3.11+, stdlib only (abc, json, subprocess, argparse, pathlib, dataclasses, signal, re).

---

## File Map

| File | Responsibility |
|------|---------------|
| `core/mailbox.py` | JSON file mailbox for agent-to-agent messages + history log |
| `core/control_queue.py` | JSON file queue for external control commands (quit) |
| `adapters/base.py` | Abstract base + AgentResult dataclass |
| `adapters/claude_code.py` | Claude Code subprocess adapter |
| `core/game_master.py` | State machine loop, prompt assembly, turn orchestration |
| `prompts/executor-base.md` | System prompt skeleton for executor role |
| `prompts/evaluator-base.md` | System prompt skeleton for evaluator role |
| `game_master.py` | CLI entry point (argparse) |

---

### Task 1: Mailbox

**Files:** Create `core/__init__.py`, `core/mailbox.py`

- [ ] **Step 1: Create core package init**

```bash
mkdir -p E:\WorkSpace\Projects\GameTool\core
```

Write `core/__init__.py`:
```python
# core package
```

- [ ] **Step 2: Write Mailbox class**

Write `core/mailbox.py`:
```python
import json
from pathlib import Path
from datetime import datetime, timezone


class Mailbox:
    """JSON file-based mailbox for agent-to-agent messages."""

    def __init__(self, work_dir: Path):
        self.mailbox_dir = work_dir / "mailbox"
        self.mailbox_dir.mkdir(parents=True, exist_ok=True)
        self._executor_inbox = self.mailbox_dir / "executor-inbox.json"
        self._evaluator_inbox = self.mailbox_dir / "evaluator-inbox.json"
        self._history_file = work_dir / "history.jsonl"

    # --- executor inbox (evaluator writes, executor reads) ---

    def put_executor_msg(self, msg: dict) -> None:
        msg["timestamp"] = datetime.now(timezone.utc).isoformat()
        self._executor_inbox.write_text(json.dumps(msg, ensure_ascii=False, indent=2), encoding="utf-8")

    def get_executor_msg(self) -> dict | None:
        if not self._executor_inbox.exists():
            return None
        return json.loads(self._executor_inbox.read_text(encoding="utf-8"))

    # --- evaluator inbox (executor writes, evaluator reads) ---

    def put_evaluator_msg(self, msg: dict) -> None:
        msg["timestamp"] = datetime.now(timezone.utc).isoformat()
        self._evaluator_inbox.write_text(json.dumps(msg, ensure_ascii=False, indent=2), encoding="utf-8")

    def get_evaluator_msg(self) -> dict | None:
        if not self._evaluator_inbox.exists():
            return None
        return json.loads(self._evaluator_inbox.read_text(encoding="utf-8"))

    # --- history ---

    def append_history(self, entry: dict) -> None:
        entry["timestamp"] = datetime.now(timezone.utc).isoformat()
        with open(self._history_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def read_history(self) -> list[dict]:
        if not self._history_file.exists():
            return []
        entries = []
        with open(self._history_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    entries.append(json.loads(line))
        return entries
```

- [ ] **Step 3: Verify**

```bash
python -c "from core.mailbox import Mailbox; print('OK')"
```
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add core/__init__.py core/mailbox.py
git commit -m "feat: add Mailbox for agent message passing"
```

---

### Task 2: ControlQueue

**Files:** Create `core/control_queue.py`

- [ ] **Step 1: Write ControlQueue class**

Write `core/control_queue.py`:
```python
import json
import os
from pathlib import Path
from datetime import datetime, timezone


class ControlQueue:
    """JSON file-based queue for external control commands.

    The queue is a JSON array of command objects in control-queue.json.
    Commands are consumed (popped) so they are processed exactly once.
    """

    def __init__(self, work_dir: Path):
        self._file = work_dir / "control-queue.json"

    def push(self, command: str) -> None:
        """Append a command to the queue."""
        msg = {"command": command, "timestamp": datetime.now(timezone.utc).isoformat()}
        queue = self._read_all() if self._file.exists() else []
        queue.append(msg)
        self._write_all(queue)

    def pop_all(self) -> list[dict]:
        """Consume and return all pending commands. Clears the queue after read."""
        if not self._file.exists():
            return []
        queue = self._read_all()
        os.remove(self._file)
        return queue

    def has_quit(self, commands: list[dict]) -> bool:
        """Check if any command in the list is 'quit'."""
        return any(c.get("command") == "quit" for c in commands)

    def _read_all(self) -> list[dict]:
        return json.loads(self._file.read_text(encoding="utf-8"))

    def _write_all(self, queue: list[dict]) -> None:
        self._file.parent.mkdir(parents=True, exist_ok=True)
        self._file.write_text(json.dumps(queue, ensure_ascii=False, indent=2), encoding="utf-8")
```

- [ ] **Step 2: Verify**

```bash
python -c "from core.control_queue import ControlQueue; print('OK')"
```
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add core/control_queue.py
git commit -m "feat: add ControlQueue for external interrupt commands"
```

---

### Task 3: AgentAdapter base + AgentResult

**Files:** Create `adapters/__init__.py`, `adapters/base.py`

- [ ] **Step 1: Create adapters package init**

```bash
mkdir -p E:\WorkSpace\Projects\GameTool\adapters
```

Write `adapters/__init__.py`:
```python
# adapters package
```

- [ ] **Step 2: Write AgentResult dataclass and AgentAdapter ABC**

Write `adapters/base.py`:
```python
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class AgentResult:
    """Result from an agent execution turn."""
    success: bool
    stdout: str
    stderr: str
    exit_code: int
    parsed: dict = field(default_factory=dict)


class AgentAdapter(ABC):
    """Abstract base for AI agent backends.

    Each adapter wraps a specific CLI (claude, codex, gemini, etc.),
    normalizing prompt building, execution, and output parsing.
    """

    @abstractmethod
    def build_prompt(self, base_prompt: str, role: str, task: str,
                     feedback: dict | None, history: list[dict]) -> str:
        """Build the full prompt to send to the agent CLI."""

    @abstractmethod
    def execute(self, prompt: str, allowed_tools: list[str],
                timeout: int) -> AgentResult:
        """Invoke the agent CLI and return raw result."""

    @abstractmethod
    def parse_output(self, output: str) -> dict:
        """Parse agent stdout into structured data.

        Returns dict with keys depending on agent role:
        - executor: {summary, files_modified, changes}
        - evaluator: {score, feedback, strengths, weaknesses}
        """
```

- [ ] **Step 3: Verify**

```bash
python -c "from adapters.base import AgentAdapter, AgentResult; print('OK')"
```
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add adapters/__init__.py adapters/base.py
git commit -m "feat: add AgentAdapter ABC and AgentResult dataclass"
```

---

### Task 4: Prompt templates

**Files:** Create `prompts/executor-base.md`, `prompts/evaluator-base.md`

- [ ] **Step 1: Write executor base prompt**

```bash
mkdir -p E:\WorkSpace\Projects\GameTool\prompts
```

Write `prompts/executor-base.md`:
```markdown
## Role: Executor

You are the Executor in an adversarial game loop. Your goal is to modify the target file(s) to satisfy the Evaluator's feedback.

### Rules
1. Read the current state of the target file(s) before making changes.
2. Make concrete edits to improve the work based on the Evaluator's last feedback.
3. After making changes, output a structured summary in this format:

```
---EXECUTOR SUMMARY---
SUMMARY: <one-line description of what you changed>
FILES: <comma-separated list of files modified>
CHANGES: <detailed description of changes made, what lines, what was changed>
---END---
```

4. If this is the first round (no Evaluator feedback yet), make your best initial attempt at the task.
5. Be thorough — every round should show meaningful improvement.
```

- [ ] **Step 2: Write evaluator base prompt**

Write `prompts/evaluator-base.md`:
```markdown
## Role: Evaluator

You are the Evaluator in an adversarial game loop. Your goal is to critically assess the Executor's work and guide them toward excellence.

### Rules
1. Read the target file(s) and the Executor's latest changes.
2. Evaluate the work objectively. Give a numerical score from 0 to 100.
3. Output your evaluation in this format:

```
---EVALUATOR SCORE---
SCORE: <integer 0-100>
FEEDBACK: <one-line summary of overall assessment>
STRENGTHS:
- <what was done well>
WEAKNESSES:
- <what needs improvement>
SUGGESTIONS:
- <concrete, actionable suggestions for the Executor>
---END---
```

4. Score only reaches 95+ when the work is truly excellent — near-perfect quality.
5. Be specific in feedback. Vague feedback leads to wasted rounds.
6. You have read-only access. Never modify files.
```

- [ ] **Step 3: Commit**

```bash
git add prompts/executor-base.md prompts/evaluator-base.md
git commit -m "feat: add executor and evaluator base system prompts"
```

---

### Task 5: ClaudeCodeAdapter

**Files:** Create `adapters/claude_code.py`

- [ ] **Step 1: Write ClaudeCodeAdapter**

Write `adapters/claude_code.py`:
```python
import re
import subprocess
from pathlib import Path

from adapters.base import AgentAdapter, AgentResult


class ClaudeCodeAdapter(AgentAdapter):
    """Adapter for Claude Code CLI via `claude -p` subprocess."""

    def __init__(self, work_dir: Path):
        self.work_dir = work_dir

    def build_prompt(self, base_prompt: str, role: str, task: str,
                     feedback: dict | None, history: list[dict]) -> str:
        parts = [base_prompt, "", f"## Your Role", role, "", f"## Task", task]

        if history:
            parts.append("")
            parts.append("## Previous Rounds Summary")
            for i, entry in enumerate(history, 1):
                parts.append(f"Round {i}: {entry.get('summary', '')}")

        if feedback:
            parts.append("")
            parts.append("## Evaluator Feedback (Latest)")
            parts.append(f"Score: {feedback.get('score', 'N/A')}/100")
            parts.append(f"Feedback: {feedback.get('feedback', '')}")
            if feedback.get("weaknesses"):
                parts.append("Weaknesses:")
                for w in feedback["weaknesses"]:
                    parts.append(f"- {w}")
            if feedback.get("suggestions"):
                parts.append("Suggestions:")
                for s in feedback["suggestions"]:
                    parts.append(f"- {s}")

        return "\n".join(parts)

    def execute(self, prompt: str, allowed_tools: list[str],
                timeout: int) -> AgentResult:
        tools_arg = ",".join(allowed_tools)
        cmd = [
            "claude", "-p", prompt,
            "--allowedTools", tools_arg,
            "--output-format", "text",
        ]
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=self.work_dir,
            )
            return AgentResult(
                success=result.returncode == 0,
                stdout=result.stdout,
                stderr=result.stderr,
                exit_code=result.returncode,
            )
        except subprocess.TimeoutExpired:
            return AgentResult(
                success=False,
                stdout="",
                stderr=f"Command timed out after {timeout}s",
                exit_code=-1,
            )

    def parse_output(self, output: str) -> dict:
        if "---EXECUTOR SUMMARY---" in output:
            return self._parse_executor(output)
        elif "---EVALUATOR SCORE---" in output:
            return self._parse_evaluator(output)
        return self._parse_fallback(output)

    def _parse_executor(self, output: str) -> dict:
        block = self._extract_block(output, "EXECUTOR SUMMARY")
        return {
            "summary": self._extract_field(block, "SUMMARY"),
            "files_modified": [
                f.strip()
                for f in self._extract_field(block, "FILES").split(",")
                if f.strip()
            ],
            "changes": self._extract_field(block, "CHANGES"),
        }

    def _parse_evaluator(self, output: str) -> dict:
        block = self._extract_block(output, "EVALUATOR SCORE")
        score_str = self._extract_field(block, "SCORE")
        try:
            score = int(re.search(r"\d+", score_str).group())
        except (AttributeError, ValueError):
            score = 0
        strengths = self._extract_list(block, "STRENGTHS")
        weaknesses = self._extract_list(block, "WEAKNESSES")
        suggestions = self._extract_list(block, "SUGGESTIONS")
        return {
            "score": score,
            "feedback": self._extract_field(block, "FEEDBACK"),
            "strengths": strengths,
            "weaknesses": weaknesses,
            "suggestions": suggestions,
        }

    def _parse_fallback(self, output: str) -> dict:
        score = 0
        m = re.search(r"(?:score|SCORE)[:：]\s*(\d+)", output)
        if m:
            score = int(m.group(1))
        return {
            "score": score,
            "feedback": output[:500],
            "strengths": [],
            "weaknesses": [],
            "suggestions": [],
            "summary": output[:500],
            "files_modified": [],
            "changes": output[:500],
        }

    def _extract_block(self, text: str, marker: str) -> str:
        pattern = rf"---{marker}---(.*?)---END---"
        m = re.search(pattern, text, re.DOTALL)
        return m.group(1).strip() if m else text

    def _extract_field(self, block: str, field: str) -> str:
        m = re.search(rf"^{field}:\s*(.+)$", block, re.MULTILINE)
        return m.group(1).strip() if m else ""

    def _extract_list(self, block: str, field: str) -> list[str]:
        lines = block.split("\n")
        items = []
        capturing = False
        for line in lines:
            if line.strip().startswith(f"{field}:"):
                capturing = True
                continue
            if capturing and line.strip().startswith("- "):
                items.append(line.strip()[2:].strip())
            elif capturing and line.strip() and not line.strip().startswith("- "):
                break
        return items
```

- [ ] **Step 2: Unit test — build_prompt**

Create `tests/adapters/test_claude_code.py`:
```python
from pathlib import Path
from adapters.claude_code import ClaudeCodeAdapter

def test_build_prompt_minimal():
    adapter = ClaudeCodeAdapter(work_dir=Path("/tmp"))
    prompt = adapter.build_prompt(
        base_prompt="You are an executor.",
        role="You are a Python expert.",
        task="Optimize main.py",
        feedback=None,
        history=[],
    )
    assert "You are an executor." in prompt
    assert "You are a Python expert." in prompt
    assert "Optimize main.py" in prompt

def test_build_prompt_with_feedback():
    adapter = ClaudeCodeAdapter(work_dir=Path("/tmp"))
    prompt = adapter.build_prompt(
        base_prompt="base",
        role="role",
        task="task",
        feedback={"score": 72, "feedback": "needs work", "weaknesses": ["slow"], "suggestions": ["use cache"]},
        history=[],
    )
    assert "72" in prompt
    assert "needs work" in prompt
    assert "slow" in prompt
    assert "use cache" in prompt

def test_build_prompt_with_history():
    adapter = ClaudeCodeAdapter(work_dir=Path("/tmp"))
    prompt = adapter.build_prompt(
        base_prompt="base",
        role="role",
        task="task",
        feedback=None,
        history=[{"summary": "Round 1: initial attempt"}, {"summary": "Round 2: improved naming"}],
    )
    assert "Round 1" in prompt
    assert "Round 2" in prompt

def test_parse_executor_output():
    adapter = ClaudeCodeAdapter(work_dir=Path("/tmp"))
    output = """---EXECUTOR SUMMARY---
SUMMARY: refactored main.py
FILES: main.py, utils.py
CHANGES: rewrote the parser
---END---"""
    parsed = adapter.parse_output(output)
    assert parsed["summary"] == "refactored main.py"
    assert parsed["files_modified"] == ["main.py", "utils.py"]
    assert parsed["changes"] == "rewrote the parser"

def test_parse_evaluator_output():
    adapter = ClaudeCodeAdapter(work_dir=Path("/tmp"))
    output = """---EVALUATOR SCORE---
SCORE: 85
FEEDBACK: good progress
STRENGTHS:
- clean code
- good tests
WEAKNESSES:
- missing docs
SUGGESTIONS:
- add docstrings
- improve naming
---END---"""
    parsed = adapter.parse_output(output)
    assert parsed["score"] == 85
    assert parsed["feedback"] == "good progress"
    assert "clean code" in parsed["strengths"]
    assert "missing docs" in parsed["weaknesses"]
    assert "add docstrings" in parsed["suggestions"]

def test_parse_fallback():
    adapter = ClaudeCodeAdapter(work_dir=Path("/tmp"))
    output = "score: 42 some random text"
    parsed = adapter.parse_output(output)
    assert parsed["score"] == 42
```

- [ ] **Step 3: Create tests package init**

```bash
mkdir -p E:\WorkSpace\Projects\GameTool\tests\adapters
```

Write `tests/__init__.py`:
```python
# tests package
```
Write `tests/adapters/__init__.py`:
```python
# tests/adapters
```

- [ ] **Step 4: Run tests**

```bash
cd E:\WorkSpace\Projects\GameTool && python -m pytest tests/adapters/test_claude_code.py -v
```
Expected: all 6 tests pass

- [ ] **Step 5: Commit**

```bash
git add adapters/claude_code.py tests/ tests/adapters/
git commit -m "feat: add ClaudeCodeAdapter with build_prompt, execute, and parse_output"
```

---

### Task 6: GameMaster

**Files:** Create `core/game_master.py`

- [ ] **Step 1: Write GameMaster class**

Write `core/game_master.py`:
```python
import signal
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from core.control_queue import ControlQueue
from core.mailbox import Mailbox
from adapters.base import AgentAdapter


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
```

- [ ] **Step 2: Verify import**

```bash
cd E:\WorkSpace\Projects\GameTool && python -c "from core.game_master import GameMaster; print('OK')"
```
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add core/game_master.py
git commit -m "feat: add GameMaster state machine loop"
```

---

### Task 7: CLI entry point

**Files:** Create `game_master.py` (project root)

- [ ] **Step 1: Write CLI entry point**

Write `game_master.py`:
```python
#!/usr/bin/env python3
"""Game Master — Dual AI Agent Adversarial Game Framework.

Usage:
    python game_master.py --task "optimize resume.md" \\
                          --target E:/project/resume.md \\
                          --executor-role templates/executor-role.md \\
                          --evaluator-role templates/evaluator-role.md

Control:
    python game_master.py --control quit --task-id <id>
"""

import argparse
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from adapters.claude_code import ClaudeCodeAdapter
from core.control_queue import ControlQueue
from core.game_master import GameMaster


def cmd_run(args):
    # Validate
    target = Path(args.target)
    if not target.exists():
        print(f"Error: target path does not exist: {target}")
        sys.exit(1)

    exec_role = Path(args.executor_role)
    eval_role = Path(args.evaluator_role)
    for f in (exec_role, eval_role):
        if not f.exists():
            print(f"Error: role file does not exist: {f}")
            sys.exit(1)

    # Check claude CLI
    import shutil
    if shutil.which("claude") is None:
        print("Error: claude CLI not found in PATH")
        sys.exit(1)

    # Setup work dir
    task_id = args.task_id or str(uuid.uuid4())[:8]
    work_root = Path(target.parent if target.is_file() else target) / ".game-master"
    work_dir = work_root / task_id
    work_dir.mkdir(parents=True, exist_ok=True)

    # Create adapter
    adapter = ClaudeCodeAdapter(work_dir=work_dir)

    # Run
    gm = GameMaster(
        task=args.task,
        target=str(target.absolute()),
        executor_role_path=exec_role.absolute(),
        evaluator_role_path=eval_role.absolute(),
        adapter=adapter,
        work_dir=work_dir,
        max_rounds=args.max_rounds,
        timeout=args.timeout,
        score_threshold=args.score_threshold,
    )
    result = gm.run()

    # Print final summary
    print()
    print(f"=== Game Over ===")
    print(f"Status: {result['status']}")
    print(f"Rounds: {result['rounds']}")
    print(f"Best Score: {result['best_score']}")
    print(f"Work Dir: {result['work_dir']}")

    return 0 if result["status"] == "completed" else 1


def cmd_control(args):
    target = Path(args.target) if args.target else Path.cwd()
    work_root = Path(target.parent if target.is_file() else target) / ".game-master"
    if args.task_id == "latest":
        dirs = sorted(work_root.glob("*"), key=lambda p: p.stat().st_mtime, reverse=True)
        work_dir = dirs[0] if dirs else None
        if not work_dir:
            print("Error: no game sessions found")
            sys.exit(1)
    else:
        work_dir = work_root / args.task_id

    cq = ControlQueue(work_dir)
    cq.push(args.control)
    print(f"Sent control command '{args.control}' to {work_dir}")


def main():
    parser = argparse.ArgumentParser(
        description="Game Master — Dual AI Agent Adversarial Game Framework"
    )
    sub = parser.add_subparsers(dest="command")

    # run
    run_parser = sub.add_parser("run", help="Start a game session")
    run_parser.add_argument("--task", required=True, help="Task description")
    run_parser.add_argument("--target", required=True, help="Target file or directory path")
    run_parser.add_argument("--executor-role", required=True, help="Path to executor role file (.md)")
    run_parser.add_argument("--evaluator-role", required=True, help="Path to evaluator role file (.md)")
    run_parser.add_argument("--max-rounds", type=int, default=10, help="Max rounds (default: 10)")
    run_parser.add_argument("--timeout", type=int, default=300, help="Agent timeout in seconds (default: 300)")
    run_parser.add_argument("--score-threshold", type=int, default=95, help="Score threshold to stop (default: 95)")
    run_parser.add_argument("--task-id", help="Custom task ID (auto-generated if omitted)")

    # control
    ctrl_parser = sub.add_parser("control", help="Send control command to a running game")
    ctrl_parser.add_argument("--control", required=True, help="Command: quit")
    ctrl_parser.add_argument("--task-id", default="latest", help="Task ID or 'latest'")
    ctrl_parser.add_argument("--target", help="Target path used when game was started")

    args = parser.parse_args()

    if args.command == "run":
        sys.exit(cmd_run(args))
    elif args.command == "control":
        cmd_control(args)
        sys.exit(0)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify CLI help**

```bash
cd E:\WorkSpace\Projects\GameTool && python game_master.py --help
```
Expected: prints usage with `run` and `control` subcommands

- [ ] **Step 3: Commit**

```bash
git add game_master.py
git commit -m "feat: add CLI entry point with run and control subcommands"
```

---

### Task 8: Example role templates

**Files:** Create `templates/executor-role.md`, `templates/evaluator-role.md`

- [ ] **Step 1: Write example templates**

```bash
mkdir -p E:\WorkSpace\Projects\GameTool\templates
```

Write `templates/executor-role.md`:
```markdown
You are a senior software engineer with deep expertise in writing clean, maintainable, and performant code. You take pride in your craft and are open to constructive feedback. Your goal is to produce the best possible output for the task at hand.

When you receive feedback from the Evaluator, address each point specifically. Do not ignore any suggestions — even if you disagree, explain your reasoning in your changes.
```

Write `templates/evaluator-role.md`:
```markdown
You are a rigorous code reviewer with 15 years of experience. You evaluate work based on:

1. **Correctness** — Does it do what it's supposed to do?
2. **Clarity** — Is the code readable and well-structured?
3. **Completeness** — Are edge cases handled?
4. **Efficiency** — Is there unnecessary complexity or waste?
5. **Style** — Does it follow conventions and best practices?

Score each aspect mentally, then give an overall score. Be honest — a 95+ means the work is genuinely excellent and production-ready. Provide concrete, actionable suggestions. Never be vague.

Important: You are a READ-ONLY evaluator. Do not modify any files. Only read and assess.
```

- [ ] **Step 2: Commit**

```bash
git add templates/executor-role.md templates/evaluator-role.md
git commit -m "docs: add example executor and evaluator role templates"
```

---

### Task 9: Integration test

**Files:** Create `tests/test_integration.py`

- [ ] **Step 1: Write integration test (mock subprocess)

Write `tests/test_integration.py`:
```python
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

        # Patch the prompts path in GameMaster.__init__
        with patch.object(GameMaster, '__init__', lambda self, **kw: None):
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
```

- [ ] **Step 2: Run integration tests**

```bash
cd E:\WorkSpace\Projects\GameTool && python -m pytest tests/test_integration.py -v
```
Expected: all 3 tests pass

- [ ] **Step 3: Run all tests**

```bash
cd E:\WorkSpace\Projects\GameTool && python -m pytest tests/ -v
```
Expected: all tests pass (6 unit + 3 integration = 9)

- [ ] **Step 4: Commit**

```bash
git add tests/test_integration.py
git commit -m "test: add integration tests for game loop, control queue, and mailbox"
```

---

## Verification Checklist

After all tasks complete:

- [ ] `python game_master.py --help` shows run/control subcommands
- [ ] `python -m pytest tests/ -v` — all tests pass
- [ ] `python game_master.py run --task "test" --target . --executor-role templates/executor-role.md --evaluator-role templates/evaluator-role.md --max-rounds 1` runs without crashing (requires `claude` CLI)
- [ ] `python game_master.py control --control quit --task-id latest` sends control command
