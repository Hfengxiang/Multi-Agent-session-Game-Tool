#!/usr/bin/env python3
"""Game Master — Dual AI Agent Adversarial Game Framework.

Usage:
    python game_master.py run --task "optimize resume.md" \\
                              --target E:/project/resume.md \\
                              --executor-role templates/executor-role.md \\
                              --evaluator-role templates/evaluator-role.md

Control:
    python game_master.py control --control quit --task-id <id>
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
