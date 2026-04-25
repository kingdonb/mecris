#!/usr/bin/env python3
"""
evaluate_aider.py — POC evaluation harness for AI framework comparison.

Runs a controlled, repeatable refactoring task using Aider (if installed)
and records timing + output quality for comparison against Claude Code metrics.

Usage:
    python scripts/evaluate_aider.py --mode refactor [--model MODEL] [--dry-run]

Modes:
    refactor   Ask the framework to extract a pure function from a target file.
               Target: ghost/narrator.py — extract the daily_walk_status logic
               into a standalone function with a unit test.

Output:
    Appends one JSONL line to experiments/ai_eval/results.jsonl:
    {
        "ts": "<ISO>",
        "framework": "aider|dry-run",
        "model": "<model-id>",
        "mode": "refactor",
        "duration_s": <float>,
        "exit_code": <int>,
        "output_lines": <int>,
        "files_changed": [<str>],
        "notes": "<str>"
    }

Tracking:
    Append each run to docs/AI_FRAMEWORK_EVALUATION.md evidence log manually.
    Compare cost via Neon autonomous_turns table or billing dashboard.

Related: kingdonb/mecris#205, yebyen/mecris#277
"""

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


RESULTS_DIR = Path("experiments/ai_eval")
RESULTS_FILE = RESULTS_DIR / "results.jsonl"

# The refactoring test prompt — stable across runs for reproducibility.
REFACTOR_PROMPT = (
    "In ghost/narrator.py, find the daily_walk_status computation logic. "
    "Extract it into a new pure function `compute_daily_walk_status(activity_data: dict) -> str` "
    "at module level (no side effects, no I/O). "
    "Add a docstring. Do not change any existing callers or function signatures. "
    "Do not add new dependencies. Run existing tests to confirm nothing breaks."
)

# Files the refactor should touch (used to validate output).
EXPECTED_FILES = {"ghost/narrator.py"}


def parse_args():
    p = argparse.ArgumentParser(description="AI framework POC evaluator")
    p.add_argument("--mode", choices=["refactor"], default="refactor",
                   help="Evaluation mode (default: refactor)")
    p.add_argument("--model", default="gpt-4o-mini",
                   help="Model ID to pass to Aider (default: gpt-4o-mini)")
    p.add_argument("--dry-run", action="store_true",
                   help="Skip actual framework invocation; record a dry-run entry")
    return p.parse_args()


def check_aider_installed() -> bool:
    result = subprocess.run(
        ["aider", "--version"], capture_output=True, text=True
    )
    return result.returncode == 0


def run_aider(mode: str, model: str) -> dict:
    """Invoke aider with the test prompt and return execution metadata."""
    start = time.monotonic()

    if mode == "refactor":
        prompt = REFACTOR_PROMPT
        target_files = ["ghost/narrator.py"]

    cmd = [
        "aider",
        "--model", model,
        "--yes",           # non-interactive
        "--no-git",        # we handle git ourselves
        "--message", prompt,
        *target_files,
    ]

    print(f"[evaluate_aider] Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=False, text=True)

    duration = time.monotonic() - start

    # Attempt to detect changed files via git diff
    diff_result = subprocess.run(
        ["git", "diff", "--name-only"], capture_output=True, text=True
    )
    files_changed = [f for f in diff_result.stdout.strip().splitlines() if f]

    return {
        "framework": "aider",
        "model": model,
        "mode": mode,
        "exit_code": result.returncode,
        "duration_s": round(duration, 2),
        "files_changed": files_changed,
        "notes": "ok" if result.returncode == 0 else "non-zero exit",
    }


def run_dry_run(mode: str, model: str) -> dict:
    """Record a dry-run entry without invoking any framework."""
    print("[evaluate_aider] Dry-run mode — no framework invoked.")
    return {
        "framework": "dry-run",
        "model": model,
        "mode": mode,
        "exit_code": 0,
        "duration_s": 0.0,
        "files_changed": [],
        "notes": "dry-run; aider not invoked",
    }


def write_result(entry: dict) -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    entry["ts"] = datetime.now(timezone.utc).isoformat()
    with RESULTS_FILE.open("a") as fh:
        fh.write(json.dumps(entry) + "\n")
    print(f"[evaluate_aider] Result written to {RESULTS_FILE}")
    print(json.dumps(entry, indent=2))


def main():
    args = parse_args()

    if args.dry_run:
        entry = run_dry_run(args.mode, args.model)
    else:
        if not check_aider_installed():
            print(
                "[evaluate_aider] ERROR: aider is not installed or not on PATH.\n"
                "  Install with: pip install aider-chat\n"
                "  Or use --dry-run to record a placeholder entry.",
                file=sys.stderr,
            )
            sys.exit(1)
        entry = run_aider(args.mode, args.model)

    write_result(entry)

    if entry.get("files_changed") and not args.dry_run:
        changed = set(entry["files_changed"])
        missing = EXPECTED_FILES - changed
        if missing:
            print(
                f"[evaluate_aider] WARNING: expected changes in {EXPECTED_FILES} "
                f"but these were not touched: {missing}"
            )
        else:
            print(f"[evaluate_aider] ✓ Expected files changed: {changed & EXPECTED_FILES}")

    return entry["exit_code"]


if __name__ == "__main__":
    sys.exit(main())
