#!/usr/bin/env python3
"""Runtime health check for Hermes + physio-hermes-ops integration.

Checks three layers:
1. cron scheduler and live jobs
2. legacy heartbeat freshness and interpretation
3. built-in memory headroom

Outputs JSON to stdout for CLI/cron/dashboard use.
"""

from __future__ import annotations

import json
import re
import sqlite3
import subprocess
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path("/home/yk/physio-hermes-ops")
HERMES_HOME = Path("/home/yk/.hermes")
HERMES_BIN = Path("/home/yk/.local/bin/hermes")
HEARTBEAT_PATH = ROOT / "lineage" / "heartbeat.json"
R_LOOP_PATH = ROOT / "lineage" / "ralph_loop_state.json"
CONFIG_PATH = HERMES_HOME / "config.yaml"
STATE_DB = HERMES_HOME / "state.db"
MEMORY_DIR = HERMES_HOME / "memories"


@dataclass
class Check:
    status: str
    summary: str
    details: dict[str, Any]


def run(cmd: list[str]) -> str:
    out = subprocess.run(cmd, check=True, text=True, capture_output=True)
    return out.stdout


def hermes_cmd(*args: str) -> list[str]:
    return [str(HERMES_BIN), *args]


def now_local() -> datetime:
    return datetime.now().astimezone()


def parse_iso(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s)
    except Exception:
        return None


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def load_memory_limit() -> int | None:
    if not CONFIG_PATH.exists():
        return None
    text = CONFIG_PATH.read_text(encoding="utf-8")
    m = re.search(r"^\s*memory_char_limit:\s*(\d+)\s*$", text, re.MULTILINE)
    return int(m.group(1)) if m else None


def load_memory_usage() -> tuple[int, dict[str, int]]:
    usage_by_file: dict[str, int] = {}
    if not MEMORY_DIR.exists():
        return 0, usage_by_file
    for path in sorted(MEMORY_DIR.glob("*.md")):
        try:
            usage_by_file[path.name] = len(path.read_text(encoding="utf-8"))
        except Exception:
            usage_by_file[path.name] = 0
    return sum(usage_by_file.values()), usage_by_file


def check_cron() -> Check:
    status_out = run(hermes_cmd("cron", "status"))
    list_out = run(hermes_cmd("cron", "list", "--all"))
    scheduler_ok = "cron jobs will fire automatically" in status_out.lower()
    active_match = re.search(r"(\d+) active job", status_out)
    active_jobs = int(active_match.group(1)) if active_match else None
    ok_count = len(re.findall(r"\bok\b", list_out))
    err_count = len(re.findall(r"\berror\b", list_out))
    next_run_match = re.search(r"Next run:\s*(.+)", status_out)
    next_run = next_run_match.group(1).strip() if next_run_match else None
    status = "ok" if scheduler_ok and (err_count == 0) else "warn"
    summary = (
        f"scheduler {'alive' if scheduler_ok else 'down'}, "
        f"active_jobs={active_jobs}, error_jobs={err_count}"
    )
    return Check(status, summary, {
        "scheduler_ok": scheduler_ok,
        "active_jobs": active_jobs,
        "jobs_with_ok_text": ok_count,
        "jobs_with_error_text": err_count,
        "next_run": next_run,
    })


def heartbeat_freshness(generated_at: str | None, max_age_minutes: int = 10) -> tuple[str, float | None]:
    dt = parse_iso(generated_at)
    if not dt:
        return "unknown", None
    age_min = (now_local() - dt.astimezone()).total_seconds() / 60.0
    return ("fresh" if age_min <= max_age_minutes else "stale"), round(age_min, 1)


def check_heartbeat() -> Check:
    hb = load_json(HEARTBEAT_PATH)
    loop = load_json(R_LOOP_PATH)
    freshness, age_min = heartbeat_freshness(hb.get("generated_at"))
    source = hb.get("source") or "unknown"
    live_cron_has_heartbeat = False
    try:
        jobs_text = (HERMES_HOME / "cron" / "jobs.json").read_text(encoding="utf-8")
        live_cron_has_heartbeat = "heartbeat" in jobs_text.lower()
    except Exception:
        pass
    loop_summary = str(loop.get("summary") or "").lower()
    retired = not live_cron_has_heartbeat and "standby" in loop_summary
    if retired:
        status = "ok"
        summary = "legacy heartbeat retired; live Hermes cron is canonical"
    elif freshness == "stale" or not live_cron_has_heartbeat:
        status = "warn"
        summary = "legacy heartbeat stale or not backed by live Hermes cron"
    else:
        status = "ok"
        summary = "heartbeat artifact looks fresh and linked"
    return Check(status, summary, {
        "heartbeat_generated_at": hb.get("generated_at"),
        "heartbeat_alive": hb.get("alive"),
        "freshness": freshness,
        "age_minutes": age_min,
        "source": source,
        "live_cron_has_heartbeat_job": live_cron_has_heartbeat,
        "retired": retired,
        "ralph_loop_generated_at": loop.get("generated_at"),
        "ralph_loop_summary": loop.get("summary"),
    })


def check_memory() -> Check:
    limit = load_memory_limit()
    used, usage_by_file = load_memory_usage()
    db_ok = STATE_DB.exists() and STATE_DB.stat().st_size > 0
    message_count = None
    latest_ts = None
    if db_ok:
        conn = sqlite3.connect(str(STATE_DB))
        cur = conn.cursor()
        cur.execute("select count(*) from messages")
        message_count = cur.fetchone()[0]
        cur.execute("select timestamp from messages order by id desc limit 1")
        row = cur.fetchone()
        latest_ts = datetime.fromtimestamp(row[0], tz=timezone.utc).astimezone().isoformat() if row else None
        conn.close()
    headroom = (limit - used) if limit is not None else None
    if headroom is None:
        status = "warn"
        summary = "memory limit unknown"
    elif headroom < 150:
        status = "warn"
        summary = f"memory headroom low ({headroom} chars)"
    else:
        status = "ok"
        summary = f"memory writable with {headroom} chars headroom"
    return Check(status, summary, {
        "state_db_ok": db_ok,
        "state_db_size": STATE_DB.stat().st_size if STATE_DB.exists() else None,
        "messages": message_count,
        "latest_message_at": latest_ts,
        "memory_char_limit": limit,
        "memory_used": used,
        "memory_headroom": headroom,
        "memory_files": usage_by_file,
    })


def main() -> None:
    report = {
        "generated_at": now_local().isoformat(),
        "cron": asdict(check_cron()),
        "heartbeat": asdict(check_heartbeat()),
        "memory": asdict(check_memory()),
    }
    statuses = [report[k]["status"] for k in ("cron", "heartbeat", "memory")]
    report["overall_status"] = "warn" if "warn" in statuses else "ok"
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
