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
