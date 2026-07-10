#!/usr/bin/env python3
"""Batch lightweight home desktop watchdog checks for Hermes.

The individual scripts stay responsible for their own checks and stay silent
when healthy. This coordinator reduces Hermes schedules while preserving those
bounded checks.
"""

from __future__ import annotations

import fcntl
import os
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path


KST = timezone(timedelta(hours=9))
SCRIPT_DIR = Path(os.environ.get("HERMES_SCRIPT_DIR", str(Path.home() / ".hermes" / "scripts")))
LOCK_PATH = Path(
    os.environ.get(
        "HOME_DESKTOP_WATCHDOG_BATCH_LOCK",
        str(Path.home() / ".local" / "state" / "physio-hermes-ops" / "home_desktop_watchdog_batch.lock"),
    )
)


def run_script(script_name: str) -> tuple[int, str]:
    script = SCRIPT_DIR / script_name
    if not script.exists():
        return 0, f"[skip] {script_name}: missing at {script}"
    if script.suffix == ".sh":
        command = ["bash", str(script)]
    else:
        command = ["python3", str(script)]
    result = subprocess.run(command, text=True, capture_output=True)
    output = (result.stdout + result.stderr).strip()
    if result.returncode == 0 and not output:
        return 0, ""
    status = "ok" if result.returncode == 0 else f"exit_{result.returncode}"
    return result.returncode, f"[{status}] {script_name}\n{output}".rstrip()


def should_run_google_token(now: datetime) -> bool:
    return os.environ.get("RUN_GOOGLE_TOKEN_WATCHDOG") == "1" or (now.hour in {7, 19} and now.minute < 10)


def should_run_research_pipeline(now: datetime) -> bool:
    return os.environ.get("RUN_RESEARCH_PIPELINE_WATCHDOG") == "1" or (now.hour == 6 and 50 <= now.minute < 60)


def main() -> int:
    now = datetime.now(KST)
    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)

    with LOCK_PATH.open("w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return 0

        tasks = [
            "hermes_ops_watchdog.py",
            "ensure-kinelo-8888.sh",
        ]
        if should_run_google_token(now):
            tasks.append("google_token_watchdog.py")
        if should_run_research_pipeline(now):
            tasks.append("rehab_research_pipeline_watchdog.py")

        outputs: list[str] = []
        failures = 0
        for task in tasks:
            code, output = run_script(task)
            failures += 1 if code else 0
            if output:
                outputs.append(output)

        if outputs:
            print(
                "[home desktop watchdog batch]\n"
                f"timestamp: {now.isoformat()}\n"
                f"scripts: {', '.join(tasks)}\n"
                f"status: {'ok' if failures == 0 else 'partial_failure'}\n"
                + "\n\n".join(outputs)
            )
        return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
