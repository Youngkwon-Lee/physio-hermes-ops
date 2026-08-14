#!/usr/bin/env python3
"""Write a home-desktop runtime health snapshot for dashboard/read-model use."""

from __future__ import annotations

import json
import os
import subprocess
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DERIVED_DIR = ROOT / "dashboard" / "derived"
LINEAGE_DIR = ROOT / "lineage"
PHYSIO_APP_ROOT = Path("/home/yk/physio_app")
MISSION_CONTROL_BASE = "http://127.0.0.1:8792"
AUTOMATION_HEALTH_PATH = DERIVED_DIR / "automation_health.json"
RUNTIME_HEALTH_SCRIPT = ROOT / "scripts" / "check_hermes_runtime_health.py"
GOOGLE_TOKEN_PATH = Path(
    os.environ.get(
        "GOOGLE_TOKEN_PATH",
        str(Path.home() / ".config/google/oauth/kwon3856_primary_token.json"),
    )
)
SNS_OUTPUT_DIR = Path(os.environ.get("REHAB_SNS_OUTPUT_DIR", str(Path.home() / ".hermes/rehab-sns")))
SNS_PACKET_SCRIPT = ROOT / "cron" / "scripts" / "rehab_sns_signal_packet.sh"


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


def check_google_auth() -> dict[str, Any]:
    """Expose Google readiness without exposing token contents."""
    if not GOOGLE_TOKEN_PATH.exists():
        return {"status": "warn", "state": "missing", "path": str(GOOGLE_TOKEN_PATH)}
    try:
        data = json.loads(GOOGLE_TOKEN_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"status": "warn", "state": "unreadable", "path": str(GOOGLE_TOKEN_PATH), "error": str(exc)}

    expiry_raw = str(data.get("expiry") or "").strip()
    has_refresh_token = bool(str(data.get("refresh_token") or "").strip())
    result: dict[str, Any] = {
        "status": "ok" if has_refresh_token else "warn",
        "state": "ready" if has_refresh_token else "refresh_token_missing",
        "path": str(GOOGLE_TOKEN_PATH),
        "has_refresh_token": has_refresh_token,
        "scope_count": len(str(data.get("scopes") or data.get("scope") or "").split()),
    }
    if expiry_raw:
        try:
            expiry = datetime.fromisoformat(expiry_raw.replace("Z", "+00:00"))
            if expiry.tzinfo is None:
                expiry = expiry.astimezone()
            minutes = int((expiry - datetime.now(expiry.tzinfo)).total_seconds() // 60)
            result["expires_at"] = expiry.isoformat(timespec="seconds")
            result["expires_in_minutes"] = minutes
            if minutes < 0:
                result.update({"status": "ok" if has_refresh_token else "warn", "state": "refreshable" if has_refresh_token else "expired"})
        except ValueError:
            result.update({"status": "warn", "state": "expiry_unreadable"})
    return result


def check_sns_collection() -> dict[str, Any]:
    """Report optional SNS collection freshness without reading account sessions."""
    packets = sorted(SNS_OUTPUT_DIR.glob("rehab-sns-signals-*.json"), key=lambda path: path.stat().st_mtime)
    result: dict[str, Any] = {
        "optional": True,
        "script_exists": SNS_PACKET_SCRIPT.exists(),
        "output_dir": str(SNS_OUTPUT_DIR),
    }
    if not SNS_PACKET_SCRIPT.exists():
        return {**result, "status": "warn", "state": "script_missing"}
    if not packets:
        return {**result, "status": "watch", "state": "no_packet"}

    latest = packets[-1]
    age_minutes = int((datetime.now().astimezone().timestamp() - latest.stat().st_mtime) // 60)
    result.update({"latest_packet": str(latest), "latest_mtime": datetime.fromtimestamp(latest.stat().st_mtime).astimezone().isoformat(timespec="seconds"), "age_minutes": age_minutes})
    try:
        payload = json.loads(latest.read_text(encoding="utf-8"))
        summary = payload.get("summary") if isinstance(payload, dict) else None
        platform_counts = {
            platform: {
                "ok": int(values.get("ok", 0)),
                "error": int(values.get("error", 0)),
                "planned": int(values.get("planned", 0)),
            }
            for platform, values in (summary or {}).items()
            if isinstance(values, dict)
        }
        result["platform_counts"] = platform_counts
        result["platform_ok_count"] = sum(item["ok"] for item in platform_counts.values())
        result["platform_error_count"] = sum(item["error"] for item in platform_counts.values())
        result["attempt_count"] = len(payload.get("results", [])) if isinstance(payload.get("results"), list) else None
    except (OSError, json.JSONDecodeError):
        result["attempt_count"] = None
    if age_minutes > 36 * 60:
        status, state = "watch", "stale"
    elif result.get("platform_error_count", 0) and not result.get("platform_ok_count", 0):
        status, state = "warn", "collection_errors"
    elif result.get("platform_error_count", 0):
        status, state = "watch", "partial_errors"
    else:
        status, state = "ok", "fresh"
    return {**result, "status": status, "state": state}


def check_physio_app_lane() -> dict[str, Any]:
    try:
        crontab_text = run_text(["crontab", "-l"])
    except subprocess.CalledProcessError as exc:
        crontab_text = exc.stdout or ""

    active_cron_lines = [
        line
        for line in crontab_text.splitlines()
        if line.strip() and not line.lstrip().startswith("#") and not line.startswith("PATH=")
    ]
    active_crontab_text = "\n".join(active_cron_lines)
    required = {
        "overnight": "automation/run_overnight.sh",
        "orchestrator": "automation/run_orchestrator_round.sh",
        "orchestrator_retry": "automation/run_orchestrator_round.sh --retry",
        "smoke_core": "automation/run_smoke_core.sh",
        "morning_report": "automation/send_morning_report.sh",
    }
    entries = {key: (needle in active_crontab_text) for key, needle in required.items()}
    active_entries = [key for key, present in entries.items() if present]

    logs = {
        "overnight_log": file_probe(PHYSIO_APP_ROOT / "automation" / "overnight.log"),
        "morning_report_log": file_probe(PHYSIO_APP_ROOT / "automation" / "morning_report.log"),
    }
    status = "warn" if active_entries else "ok"
    return {
        "status": status,
        "summary": "legacy physio_app cron disabled" if not active_entries else "legacy physio_app cron still active",
        "entries": entries,
        "active_entries": active_entries,
        "logs": logs,
    }


def build_markdown(payload: dict[str, Any]) -> str:
    runtime = payload["runtime"]
    mc = payload["mission_control"]
    physio_app = payload["physio_app"]
    automation = payload["automation"]
    google_auth = payload["google_auth"]
    sns_collection = payload["sns_collection"]
    lines = [
        "# Runtime Health Snapshot",
        "",
        f"- generated_at: {payload['generated_at']}",
        f"- overall_status: {payload['overall_status']}",
        f"- runtime_status: {runtime.get('overall_status', 'unknown')}",
        f"- mission_control_status: {mc.get('status', 'unknown')}",
        f"- physio_app_status: {physio_app.get('status', 'unknown')}",
        f"- google_auth_status: {google_auth.get('status', 'unknown')}",
        f"- google_auth_state: {google_auth.get('state', 'unknown')}",
        f"- sns_collection_status: {sns_collection.get('status', 'unknown')}",
        f"- sns_collection_state: {sns_collection.get('state', 'unknown')}",
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
    google_auth = check_google_auth()
    sns_collection = check_sns_collection()

    states = [
        runtime.get("overall_status", "warn"),
        mission_control.get("status", "warn"),
        physio_app.get("status", "warn"),
        google_auth.get("status", "warn"),
    ]
    overall = "warn" if "warn" in states else "ok"

    payload = {
        "generated_at": now_iso(),
        "overall_status": overall,
        "runtime": runtime,
        "automation": automation,
        "mission_control": mission_control,
        "physio_app": physio_app,
        "google_auth": google_auth,
        "sns_collection": sns_collection,
    }
    write_json(DERIVED_DIR / "runtime_health_snapshot.json", payload)
    (LINEAGE_DIR / "runtime_health_snapshot.md").write_text(build_markdown(payload), encoding="utf-8")
    print(str(DERIVED_DIR / "runtime_health_snapshot.json"))


if __name__ == "__main__":
    main()
