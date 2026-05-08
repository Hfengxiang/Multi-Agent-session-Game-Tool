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
