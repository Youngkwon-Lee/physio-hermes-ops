#!/usr/bin/env python3
"""Write a home-desktop runtime health snapshot for dashboard/read-model use."""

from __future__ import annotations

import json
import subprocess
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path("/home/yk/physio-hermes-ops")
DERIVED_DIR = ROOT / "dashboard" / "derived"
LINEAGE_DIR = ROOT / "lineage"
PHYSIO_APP_ROOT = Path("/home/yk/physio_app")
MISSION_CONTROL_BASE = "http://127.0.0.1:8792"
AUTOMATION_HEALTH_PATH = DERIVED_DIR / "automation_health.json"
RUNTIME_HEALTH_SCRIPT = ROOT / "scripts" / "check_hermes_runtime_health.py"
CONTROL_CENTER_READ_MODEL_SCRIPT = ROOT / "scripts" / "build_automation_control_center_read_model.py"


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def run_text(cmd: list[str]) -> str:
    return subprocess.run(cmd, check=True, text=True, capture_output=True).stdout


def run_json(cmd: list[str]) -> dict[str, Any]:
    return json.loads(run_text(cmd))


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def fetch_json(url: str) -> dict[str, Any]:
    req = urllib.request.Request(url, headers={"User-Agent": "physio-hermes-ops/health-snapshot"})
    with urllib.request.urlopen(req, timeout=5) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_json_allow_http_error(url: str) -> tuple[dict[str, Any], int]:
    req = urllib.request.Request(url, headers={"User-Agent": "physio-hermes-ops/health-snapshot"})
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read().decode("utf-8")), resp.status
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8")
        try:
            return json.loads(body), exc.code
        except json.JSONDecodeError:
            raise


def check_mission_control() -> dict[str, Any]:
    try:
        health = fetch_json(f"{MISSION_CONTROL_BASE}/health")
        actions, actions_status = fetch_json_allow_http_error(f"{MISSION_CONTROL_BASE}/mission-actions?limit=5")
        plans, plans_status = fetch_json_allow_http_error(f"{MISSION_CONTROL_BASE}/plans?limit=5")
        tasks, tasks_status = fetch_json_allow_http_error(f"{MISSION_CONTROL_BASE}/tasks?limit=5")
        endpoint_statuses = {
            "mission_actions": actions_status,
            "plans": plans_status,
            "tasks": tasks_status,
        }
        endpoints_reachable = all(code in {200, 400} for code in endpoint_statuses.values())
        return {
            "status": "ok" if endpoints_reachable else "warn",
            "health": health,
            "endpoint_statuses": endpoint_statuses,
            "counts": {
                "recent_actions": len(actions.get("items", [])) if isinstance(actions.get("items"), list) else None,
                "recent_plans": len(plans.get("items", [])) if isinstance(plans.get("items"), list) else None,
                "recent_tasks": len(tasks.get("items", [])) if isinstance(tasks.get("items"), list) else None,
            },
            "notes": [
                "400 on list endpoints is acceptable here when Mission Control requires organizationId for collection routes.",
            ],
        }
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        return {
            "status": "warn",
            "summary": "mission control unavailable",
            "error": str(exc),
        }


def file_probe(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"exists": False}
    stat = path.stat()
    return {
        "exists": True,
        "mtime": datetime.fromtimestamp(stat.st_mtime).astimezone().isoformat(timespec="seconds"),
        "size": stat.st_size,
    }


def check_physio_app_lane() -> dict[str, Any]:
    try:
        crontab_text = run_text(["crontab", "-l"])
    except subprocess.CalledProcessError as exc:
        crontab_text = exc.stdout or ""

    required = {
        "overnight": "automation/run_overnight.sh",
        "orchestrator": "automation/run_orchestrator_round.sh",
        "orchestrator_retry": "automation/run_orchestrator_round.sh --retry",
        "smoke_core": "automation/run_smoke_core.sh",
        "morning_report": "automation/send_morning_report.sh",
    }
    entries = {key: (needle in crontab_text) for key, needle in required.items()}
    missing = [key for key, present in entries.items() if not present]

    logs = {
        "overnight_log": file_probe(PHYSIO_APP_ROOT / "automation" / "overnight.log"),
        "morning_report_log": file_probe(PHYSIO_APP_ROOT / "automation" / "morning_report.log"),
    }
    status = "ok" if not missing else "warn"
    return {
        "status": status,
        "summary": "physio_app cron present" if not missing else "physio_app cron gap detected",
        "entries": entries,
        "missing_entries": missing,
        "logs": logs,
    }


def build_markdown(payload: dict[str, Any]) -> str:
    runtime = payload["runtime"]
    mc = payload["mission_control"]
    physio_app = payload["physio_app"]
    automation = payload["automation"]
    lines = [
        "# Runtime Health Snapshot",
        "",
        f"- generated_at: {payload['generated_at']}",
        f"- overall_status: {payload['overall_status']}",
        f"- runtime_status: {runtime.get('overall_status', 'unknown')}",
        f"- mission_control_status: {mc.get('status', 'unknown')}",
        f"- physio_app_status: {physio_app.get('status', 'unknown')}",
        f"- automation_total: {automation.get('summary', {}).get('total', 0)}",
        f"- automation_pass: {automation.get('summary', {}).get('pass', 0)}",
        f"- automation_watch: {automation.get('summary', {}).get('watch', 0)}",
        f"- automation_check: {automation.get('summary', {}).get('check', 0)}",
        f"- automation_fail: {automation.get('summary', {}).get('fail', 0)}",
        "",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    runtime = run_json(["python3", str(RUNTIME_HEALTH_SCRIPT)])
    automation = read_json(AUTOMATION_HEALTH_PATH)
    mission_control = check_mission_control()
    physio_app = check_physio_app_lane()

    states = [
        runtime.get("overall_status", "warn"),
        mission_control.get("status", "warn"),
        physio_app.get("status", "warn"),
    ]
    overall = "warn" if "warn" in states else "ok"

    payload = {
        "generated_at": now_iso(),
        "overall_status": overall,
        "runtime": runtime,
        "automation": automation,
        "mission_control": mission_control,
        "physio_app": physio_app,
    }
    write_json(DERIVED_DIR / "runtime_health_snapshot.json", payload)
    subprocess.run(["python3", str(CONTROL_CENTER_READ_MODEL_SCRIPT)], check=False)
    (LINEAGE_DIR / "runtime_health_snapshot.md").write_text(build_markdown(payload), encoding="utf-8")
    print(str(DERIVED_DIR / "runtime_health_snapshot.json"))


if __name__ == "__main__":
    main()
