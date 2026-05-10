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
        import shutil
        claude_path = shutil.which("claude") or "claude"
        tools_arg = ",".join(allowed_tools)
        cmd = [
            claude_path, "-p", prompt,
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
                encoding="utf-8",
                errors="replace",
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
