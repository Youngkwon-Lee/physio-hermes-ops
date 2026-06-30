#!/usr/bin/env python3
"""Batch second-brain Git sync jobs for the home desktop Hermes runner."""

from __future__ import annotations

import fcntl
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path


KST = timezone(timedelta(hours=9))
DEFAULT_SCRIPT_DIR = Path(os.environ.get("HERMES_SCRIPT_DIR", str(Path.home() / ".hermes" / "scripts")))
LOCK_PATH = Path(
    os.environ.get(
        "SECOND_BRAIN_GIT_SYNC_BATCH_LOCK",
        str(Path.home() / ".local" / "state" / "physio-hermes-ops" / "second_brain_git_sync_batch.lock"),
    )
)


def run_script(script_name: str) -> tuple[int, str]:
    script = DEFAULT_SCRIPT_DIR / script_name
    if not script.exists():
        return 0, f"[skip] {script_name}: missing at {script}"
    env = os.environ.copy()
    env.setdefault("SECOND_BRAIN_DIR", "/home/yk/brain-linux")
    env.setdefault("WINDOWS_OBSIDIAN_BRAIN_DIR", "/mnt/c/Users/82106/Documents/brain")
    result = subprocess.run([sys.executable, str(script)], text=True, capture_output=True, env=env)
    output = (result.stdout + result.stderr).strip()
    status = "ok" if result.returncode == 0 else f"exit_{result.returncode}"
    return result.returncode, f"[{status}] {script_name}\n{output}".rstrip()


def should_run_raw() -> bool:
    return os.environ.get("SKIP_RAW_HANDOFF_SYNC") != "1"


def should_run_notion_candidates(now: datetime) -> bool:
    if os.environ.get("RUN_NOTION_CANDIDATE_SYNC") == "1":
        return True
    return now.hour == 6 and now.minute < 45


def main() -> int:
    now = datetime.now(KST)
    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOCK_PATH.open("w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print("[second-brain git sync batch]\nstatus: skipped\nreason: previous run still active")
            return 0

        tasks = []
        if should_run_raw():
            tasks.append("raw_handoff_digest_git_sync.py")
        tasks.append("second_brain_safe_sync.py")
        if should_run_notion_candidates(now):
            tasks.append("notion_brain_candidate_git_sync.py")
        tasks.append("windows_obsidian_mirror_pull.py")

        failures = 0
        outputs: list[str] = []
        for task in tasks:
            code, output = run_script(task)
            failures += 1 if code else 0
            outputs.append(output)

        print(
            "[second-brain git sync batch]\n"
            f"timestamp: {now.isoformat()}\n"
            f"scripts: {', '.join(tasks)}\n"
            f"status: {'ok' if failures == 0 else 'partial_failure'}\n"
            + "\n\n".join(outputs)
        )
        return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
