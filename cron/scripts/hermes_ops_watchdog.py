#!/usr/bin/env python3
"""Hermes ops watchdog (public-safe source).

Silent-by-default no_agent cron script for lightweight Hermes runtime checks.
Prints nothing on healthy state; prints a short alert on gateway/cron issues.

Expected runtime pattern:
- schedule: every 10m (or similar)
- no_agent: true
- delivery: operator thread/channel
"""

from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

JOBS_PATH = Path(os.environ.get("HERMES_CRON_JOBS_PATH", Path.home() / ".hermes/cron/jobs.json"))
OVERDUE_GRACE_MINUTES = int(os.environ.get("HERMES_WATCHDOG_OVERDUE_MINUTES", "20"))
GATEWAY_UNIT = os.environ.get("HERMES_GATEWAY_UNIT", "hermes-gateway")
IGNORE_JOB_NAMES = {"hermes-gateway-watchdog", "hermes-ops-watchdog"}


def run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True)


def now_str() -> str:
    return datetime.now().astimezone().strftime("%F %T %Z")


def systemd_value(prop: str) -> str:
    p = run(["systemctl", "--user", "show", GATEWAY_UNIT, "-p", prop, "--value"])
    return (p.stdout or "").strip()


def gateway_issue_lines() -> list[str]:
    active = systemd_value("ActiveState")
    sub = systemd_value("SubState")
    pid = systemd_value("MainPID")
    started = systemd_value("ExecMainStartTimestamp")
    if active == "active" and sub == "running" and pid not in {"", "0"}:
        return []
    status = run(["systemctl", "--user", "status", GATEWAY_UNIT, "--no-pager", "--lines=20"])
    return [
        "[Hermes Ops Watchdog]",
        f"time: {now_str()}",
        f"gateway: {active or 'unknown'}/{sub or 'unknown'}",
        f"pid: {pid or 'unknown'}",
        f"started: {started or 'unknown'}",
        "",
        status.stdout.strip() or "(no systemctl status output)",
    ]


def parse_dt(value: str | None):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except Exception:
        return None


def cron_issue_lines() -> list[str]:
    if not JOBS_PATH.exists():
        return ["[Hermes Ops Watchdog]", f"time: {now_str()}", f"cron: jobs file missing: {JOBS_PATH}"]

    data: dict[str, Any] = json.loads(JOBS_PATH.read_text())
    jobs = data.get("jobs", [])
    now = datetime.now(timezone.utc).astimezone()
    overdue: list[dict[str, Any]] = []
    errored: list[dict[str, Any]] = []

    for job in jobs:
        if not job.get("enabled", False):
            continue
        name = job.get("name") or job.get("id") or "(unnamed)"
        if name in IGNORE_JOB_NAMES:
            continue

        last_status = job.get("last_status")
        last_delivery_error = job.get("last_delivery_error")
        last_error = job.get("last_error")
        next_run = parse_dt(job.get("next_run_at"))

        if last_status not in {None, "ok"} or last_error or last_delivery_error:
            errored.append(
                {
                    "name": name,
                    "id": job.get("id"),
                    "last_status": last_status,
                    "last_error": last_error,
                    "last_delivery_error": last_delivery_error,
                    "last_run_at": job.get("last_run_at"),
                }
            )

        if next_run is not None:
            delta_min = (now - next_run).total_seconds() / 60.0
            if delta_min > OVERDUE_GRACE_MINUTES:
                overdue.append(
                    {
                        "name": name,
                        "id": job.get("id"),
                        "minutes_overdue": round(delta_min, 1),
                        "next_run_at": job.get("next_run_at"),
                        "last_run_at": job.get("last_run_at"),
                        "last_status": last_status,
                    }
                )

    if not overdue and not errored:
        return []

    lines = ["[Hermes Ops Watchdog]", f"time: {now_str()}"]
    if overdue:
        lines.append(f"cron overdue jobs (> {OVERDUE_GRACE_MINUTES}m): {len(overdue)}")
        for item in overdue[:10]:
            lines.append(
                f"- {item['name']} ({item['id']}): overdue {item['minutes_overdue']}m | next={item['next_run_at']} | last={item['last_run_at']} | status={item['last_status']}"
            )
    if errored:
        lines.append(f"cron errored jobs: {len(errored)}")
        for item in errored[:10]:
            err = item["last_delivery_error"] or item["last_error"] or ""
            err = " ".join(str(err).split())[:200]
            lines.append(
                f"- {item['name']} ({item['id']}): status={item['last_status']} | last={item['last_run_at']} | error={err}"
            )
    return lines


def main() -> None:
    lines = gateway_issue_lines()
    if lines:
        print("\n".join(lines))
        return
    lines = cron_issue_lines()
    if lines:
        print("\n".join(lines))


if __name__ == "__main__":
    main()
