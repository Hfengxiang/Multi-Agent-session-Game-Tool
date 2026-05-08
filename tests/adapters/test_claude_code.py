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
