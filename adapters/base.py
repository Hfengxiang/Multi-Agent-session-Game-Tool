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
