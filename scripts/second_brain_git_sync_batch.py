#!/usr/bin/env python3
"""Batch second-brain Git sync jobs for the home desktop Hermes runner."""

from __future__ import annotations

import fcntl
import os
import subprocess
import sys
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path


KST = timezone(timedelta(hours=9))
DEFAULT_SCRIPT_DIR = Path(os.environ.get("HERMES_SCRIPT_DIR", str(Path.home() / ".hermes" / "scripts")))
MANIFEST_DIR = Path(os.environ.get("AUTOMATION_MANIFEST_DIR", "/home/yk/physio-hermes-ops/dashboard/runtime/automation_job_manifests"))
JOB_ID = "291191b0acd7"
JOB_NAME = "30분마다 second-brain Git 동기화 묶음"

LOCK_PATH = Path(
    os.environ.get(
        "SECOND_BRAIN_GIT_SYNC_BATCH_LOCK",
        str(Path.home() / ".local" / "state" / "physio-hermes-ops" / "second_brain_git_sync_batch.lock"),
    )
)


def write_manifest(started_at: datetime, tasks: list[str], outputs: list[str], failures: int, skipped_reason: str | None = None) -> None:
    finished_at = datetime.now(KST)
    payload = {
        "schemaVersion": 1,
        "evidenceSource": "runtime-direct",
        "generatedAt": finished_at.isoformat(),
        "runStartedAt": started_at.isoformat(),
        "runFinishedAt": finished_at.isoformat(),
        "status": "skipped" if skipped_reason else ("error" if failures else "ok"),
        "job": {"id": JOB_ID, "name": JOB_NAME, "runtime": "hermes-script"},
        "createdFiles": [],
        "notionPages": [],
        "discordMessages": [],
        "artifacts": [],
        "errors": [] if failures == 0 else [line for line in outputs if line.startswith("[exit_")],
        "metadata": {
            "tasks": tasks,
            "taskCount": len(tasks),
            "failureCount": failures,
            "skippedReason": skipped_reason,
            "outputs": outputs,
        },
    }
    MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
    path = MANIFEST_DIR / f"{JOB_ID}.json"
    tmp_path = path.with_suffix(".json.tmp")
    tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp_path.replace(path)


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
    started_at = now
    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOCK_PATH.open("w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print("[second-brain git sync batch]\nstatus: skipped\nreason: previous run still active")
            write_manifest(started_at, [], [], 0, "previous run still active")
            return 0

        tasks = []
        # Candidate files are narrow managed outputs and must be pushed first;
        # otherwise they remain untracked and block broader raw/safe sync jobs.
        tasks.append("notion_brain_candidate_git_sync.py")
        tasks.append("auto_apply_notes_git_sync.py")
        if should_run_raw():
            tasks.append("raw_handoff_digest_git_sync.py")
        tasks.append("second_brain_safe_sync.py")
        tasks.append("windows_obsidian_managed_candidate_push.py")
        tasks.append("windows_obsidian_mirror_pull.py")

        failures = 0
        outputs: list[str] = []
        for task in tasks:
            code, output = run_script(task)
            failures += 1 if code else 0
            outputs.append(output)

        write_manifest(started_at, tasks, outputs, failures)
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
