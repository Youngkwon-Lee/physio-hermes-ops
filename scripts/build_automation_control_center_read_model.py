#!/usr/bin/env python3
"""Build Automation Control Center read model JSON for Kinelo Ops."""

from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    tomllib = None


ROOT = Path("/home/yk/physio-hermes-ops")
DERIVED_DIR = ROOT / "dashboard" / "derived"
HERMES_HOME = Path("/home/yk/.hermes")
BRAIN_DIR = Path("/home/yk/brain")
WINDOWS_CODEX_AUTOMATIONS_DIR = Path("/mnt/c/Users/82106/.codex/automations")
MACBOOK_LAUNCHAGENT_SNAPSHOT_PATH = BRAIN_DIR / "operations" / "cache" / "macbook-launchagents-status.json"
PHYSIO_APP_DIR = Path("/home/yk/physio_app")
GITHUB_WORKFLOW_DIRS = [
    Path("/home/yk/kinelo-ops/.github/workflows"),
    Path("/home/yk/physio_app/.github/workflows"),
    Path("/home/yk/brain/.github/workflows"),
]
OUT_PATH = DERIVED_DIR / "automation_control_center_read_model.json"

PLANE_META: dict[str, dict[str, str]] = {
    "desktop_hermes": {
        "name": "Desktop Hermes",
        "host": "DESKTOP-T43SN5M",
        "runtimeFamily": "hermes-cron",
        "owner": "home-desktop",
    },
    "macbook_launchagents": {
        "name": "MacBook LaunchAgents",
        "host": "MacBook",
        "runtimeFamily": "launchd",
        "owner": "macbook",
    },
    "desktop_codex_automations": {
        "name": "Desktop Codex Automations",
        "host": "DESKTOP-T43SN5M",
        "runtimeFamily": "codex-automation",
        "owner": "home-desktop",
    },
    "desktop_physio_app": {
        "name": "Desktop physio_app Cron",
        "host": "DESKTOP-T43SN5M",
        "runtimeFamily": "cron",
        "owner": "home-desktop",
    },
    "windows_scheduled_tasks": {
        "name": "Windows Scheduled Tasks",
        "host": "DESKTOP-T43SN5M",
        "runtimeFamily": "windows-task-scheduler",
        "owner": "home-desktop",
    },
    "github_actions": {
        "name": "GitHub Actions",
        "host": "github.com",
        "runtimeFamily": "github-actions",
        "owner": "github",
    },
}

PIPELINE_META: dict[str, dict[str, Any]] = {
    "discord_digest": {
        "name": "Discord Digest",
        "description": "Discord conversation digest and long-term memory candidate curation.",
        "primaryPlaneId": "desktop_hermes",
        "stage": "delivery",
        "stages": ["ingest", "processing", "storage", "delivery"],
        "input": ["discord-threads", "conversation-history"],
        "output": ["discord-digest", "candidate-note", "handoff-note"],
        "ssot": "second-brain",
        "impactClass": "medium",
        "disableSafe": False,
    },
    "continuity_handoff": {
        "name": "Continuity Handoff",
        "description": "Continuity raw handoff generation and downstream sync.",
        "primaryPlaneId": "desktop_hermes",
        "stage": "storage",
        "stages": ["processing", "storage", "delivery"],
        "input": ["conversation-summaries", "ops-context"],
        "output": ["raw-handoff-markdown", "dashboard-notification"],
        "ssot": "second-brain",
        "impactClass": "medium",
        "disableSafe": False,
    },
    "event_research_capture": {
        "name": "Event & Research Capture",
        "description": "Capture event, research, and opportunity signals into durable ops memory.",
        "primaryPlaneId": "desktop_hermes",
        "stage": "processing",
        "stages": ["capture", "ingest", "processing", "storage", "delivery"],
        "input": ["event-platforms", "research-feeds", "zotero-local-api"],
        "output": ["ops-note", "candidate-note", "literature-note", "table-row"],
        "ssot": "second-brain",
        "impactClass": "high",
        "disableSafe": False,
    },
    "calendar_mail_brief": {
        "name": "Calendar & Mail Brief",
        "description": "Operational brief based on Gmail and Calendar.",
        "primaryPlaneId": "desktop_hermes",
        "stage": "delivery",
        "stages": ["capture", "processing", "delivery"],
        "input": ["gmail", "calendar"],
        "output": ["brief-message"],
        "ssot": "gmail",
        "impactClass": "medium",
        "disableSafe": False,
    },
    "news_brief": {
        "name": "News Brief",
        "description": "Daily AI or industry briefing and discussion kickoff.",
        "primaryPlaneId": "desktop_hermes",
        "stage": "delivery",
        "stages": ["capture", "processing", "delivery"],
        "input": ["news-feeds"],
        "output": ["brief-message", "discussion-kickoff"],
        "ssot": "local-runtime",
        "impactClass": "low",
        "disableSafe": True,
    },
    "convenience_brief": {
        "name": "Convenience Brief",
        "description": "Convenience-only briefing lane without default durable memory.",
        "primaryPlaneId": "desktop_hermes",
        "stage": "delivery",
        "stages": ["processing", "delivery"],
        "input": ["route-context", "ops-context"],
        "output": ["ephemeral-message"],
        "ssot": "local-runtime",
        "impactClass": "low",
        "disableSafe": True,
    },
    "memory_capture": {
        "name": "Memory Capture",
        "description": "MacBook-local source-adjacent raw capture.",
        "primaryPlaneId": "macbook_launchagents",
        "stage": "capture",
        "stages": ["capture", "ingest"],
        "input": ["notes", "screenshots", "browser-history", "shortcuts"],
        "output": ["raw-delta", "capture-metadata"],
        "ssot": "second-brain",
        "impactClass": "high",
        "disableSafe": False,
    },
    "chatgpt_capture": {
        "name": "ChatGPT Capture",
        "description": "ChatGPT and Codex conversation capture into candidate notes.",
        "primaryPlaneId": "desktop_codex_automations",
        "stage": "processing",
        "stages": ["capture", "processing", "storage"],
        "input": ["chatgpt-browser", "codex-deltas"],
        "output": ["candidate-note"],
        "ssot": "second-brain",
        "impactClass": "medium",
        "disableSafe": False,
    },
    "gmail_digest": {
        "name": "Gmail Digest",
        "description": "Gmail noise cleanup and actionable digest generation.",
        "primaryPlaneId": "desktop_codex_automations",
        "stage": "processing",
        "stages": ["capture", "processing", "storage"],
        "input": ["gmail"],
        "output": ["digest-candidate", "gmail-label-action"],
        "ssot": "gmail",
        "impactClass": "medium",
        "disableSafe": False,
    },
    "research_literature_ingest": {
        "name": "Research Literature Ingest",
        "description": "Zotero snapshot capture and literature note ingest.",
        "primaryPlaneId": "desktop_hermes",
        "stage": "storage",
        "stages": ["capture", "ingest", "processing", "storage"],
        "input": ["zotero-local-api"],
        "output": ["inventory-snapshot", "literature-note"],
        "ssot": "second-brain",
        "impactClass": "medium",
        "disableSafe": False,
    },
    "memory_review": {
        "name": "Memory Review",
        "description": "Candidate review and canonical memory promotion.",
        "primaryPlaneId": "desktop_codex_automations",
        "stage": "storage",
        "stages": ["processing", "storage", "delivery"],
        "input": ["candidate-notes"],
        "output": ["apply-note", "canonical-patch"],
        "ssot": "second-brain",
        "impactClass": "high",
        "disableSafe": False,
    },
    "runtime_watchdog": {
        "name": "Runtime Watchdog",
        "description": "Runtime health, sync, and watchdog automation.",
        "primaryPlaneId": "desktop_hermes",
        "stage": "watchdog",
        "stages": ["watchdog", "delivery"],
        "input": ["runtime-state"],
        "output": ["health-snapshot", "alert"],
        "ssot": "physio-hermes-ops",
        "impactClass": "medium",
        "disableSafe": False,
    },
    "desktop_physio_app_ops": {
        "name": "physio_app Operations",
        "description": "Home desktop physio_app scheduled orchestration, smoke checks, overnight jobs, and morning report.",
        "primaryPlaneId": "desktop_physio_app",
        "stage": "processing",
        "stages": ["processing", "delivery", "watchdog"],
        "input": ["physio_app-runtime", "supabase", "local-logs"],
        "output": ["ops-log", "morning-report", "smoke-status"],
        "ssot": "physio_app",
        "impactClass": "high",
        "disableSafe": False,
    },
    "windows_bootstrap": {
        "name": "Windows Bootstrap",
        "description": "Windows host bootstrap and scheduled integration tasks that support WSL/Hermes/Codex operations.",
        "primaryPlaneId": "windows_scheduled_tasks",
        "stage": "watchdog",
        "stages": ["watchdog", "processing"],
        "input": ["windows-task-scheduler"],
        "output": ["host-state", "runtime-bootstrap"],
        "ssot": "windows-task-scheduler",
        "impactClass": "medium",
        "disableSafe": False,
    },
    "github_ci_cd": {
        "name": "GitHub CI/CD",
        "description": "Repository workflow definitions for CI, release, preview, OCR, and operational gates.",
        "primaryPlaneId": "github_actions",
        "stage": "watchdog",
        "stages": ["watchdog", "processing", "delivery"],
        "input": ["repository-events", "manual-dispatch"],
        "output": ["check-run", "deployment", "artifact"],
        "ssot": "github",
        "impactClass": "medium",
        "disableSafe": False,
    },
}

JOB_META: dict[str, dict[str, Any]] = {
    "daily-conversation-curator": {"pipelineId": "discord_digest", "stage": "processing", "ssot": "second-brain", "costClass": "medium", "disableSafe": False, "optional": False},
    "daily-discord-digest": {"pipelineId": "discord_digest", "stage": "delivery", "ssot": "second-brain", "costClass": "medium", "disableSafe": False, "optional": False},
    "daily-discord-action-stager": {"pipelineId": "discord_digest", "stage": "processing", "ssot": "physio-hermes-ops", "costClass": "low", "disableSafe": False, "optional": False},
    "daily-discord-digest-postsync": {"pipelineId": "discord_digest", "stage": "storage", "ssot": "second-brain", "costClass": "low", "disableSafe": False, "optional": False},
    "raw-handoff-digest": {"pipelineId": "continuity_handoff", "stage": "processing", "ssot": "second-brain", "costClass": "low", "disableSafe": False, "optional": False},
    "continuity-handoff-notifier": {"pipelineId": "continuity_handoff", "stage": "delivery", "ssot": "physio-hermes-ops", "costClass": "low", "disableSafe": False, "optional": False},
    "second-brain-raw-handoff-git-sync": {"pipelineId": "continuity_handoff", "stage": "storage", "ssot": "second-brain", "costClass": "low", "disableSafe": False, "optional": False},
    "daily-event-platform-radar": {"pipelineId": "event_research_capture", "stage": "capture", "ssot": "second-brain", "costClass": "medium", "disableSafe": False, "optional": False},
    "biz-support-radar-daily": {"pipelineId": "event_research_capture", "stage": "capture", "ssot": "second-brain", "costClass": "medium", "disableSafe": False, "optional": False},
    "daily-rehab-ai-research-brief": {"pipelineId": "event_research_capture", "stage": "delivery", "ssot": "second-brain", "costClass": "medium", "disableSafe": False, "optional": False},
    "weekly-zotero-literature-ingest": {"pipelineId": "research_literature_ingest", "stage": "ingest", "ssot": "second-brain", "costClass": "medium", "disableSafe": False, "optional": False},
    "second-brain-zotero-literature-git-sync": {"pipelineId": "research_literature_ingest", "stage": "storage", "ssot": "second-brain", "costClass": "low", "disableSafe": False, "optional": False},
    "daily-calendar-mail-brief": {"pipelineId": "calendar_mail_brief", "stage": "delivery", "ssot": "gmail", "costClass": "medium", "disableSafe": False, "optional": False},
    "home-rehab-morning-brief": {"pipelineId": "calendar_mail_brief", "stage": "delivery", "ssot": "local-runtime", "costClass": "low", "disableSafe": True, "optional": True},
    "daily-ai-news-briefing": {"pipelineId": "news_brief", "stage": "delivery", "ssot": "local-runtime", "costClass": "medium", "disableSafe": True, "optional": True},
    "daily-ai-news-discussion-kickoff": {"pipelineId": "news_brief", "stage": "delivery", "ssot": "local-runtime", "costClass": "low", "disableSafe": True, "optional": True},
    "home-rehab-lunch-recommendation": {"pipelineId": "convenience_brief", "stage": "delivery", "ssot": "local-runtime", "costClass": "low", "disableSafe": True, "optional": True},
    "weekly-pt-kpi-brief": {"pipelineId": "convenience_brief", "stage": "delivery", "ssot": "local-runtime", "costClass": "low", "disableSafe": True, "optional": True},
    "chatgpt-browser-candidate-capture": {"pipelineId": "chatgpt_capture", "stage": "capture", "ssot": "second-brain", "costClass": "medium", "disableSafe": False, "optional": False},
    "second-brain-nightly-capture-and-sync": {"pipelineId": "memory_review", "stage": "storage", "ssot": "second-brain", "costClass": "medium", "disableSafe": False, "optional": False},
    "second-brain-weekly-candidate-promotion-review": {"pipelineId": "memory_review", "stage": "storage", "ssot": "second-brain", "costClass": "medium", "disableSafe": False, "optional": False},
    "weekly-promotion-review": {"pipelineId": "memory_review", "stage": "storage", "ssot": "second-brain", "costClass": "low", "disableSafe": False, "optional": False},
    "weekly-auto-apply-note": {"pipelineId": "memory_review", "stage": "storage", "ssot": "second-brain", "costClass": "low", "disableSafe": False, "optional": False},
    "weekly-apply-nudge": {"pipelineId": "memory_review", "stage": "delivery", "ssot": "second-brain", "costClass": "low", "disableSafe": False, "optional": False},
    "second-brain-candidate-git-sync": {"pipelineId": "memory_review", "stage": "storage", "ssot": "second-brain", "costClass": "low", "disableSafe": False, "optional": False},
    "gmail-github-noise-labeler": {"pipelineId": "gmail_digest", "stage": "processing", "ssot": "gmail", "costClass": "low", "disableSafe": False, "optional": False},
    "gmail-important-action-digest": {"pipelineId": "gmail_digest", "stage": "processing", "ssot": "second-brain", "costClass": "medium", "disableSafe": False, "optional": False},
    "hermes-ops-watchdog": {"pipelineId": "runtime_watchdog", "stage": "watchdog", "ssot": "physio-hermes-ops", "costClass": "low", "disableSafe": False, "optional": False},
    "google-token-watchdog": {"pipelineId": "runtime_watchdog", "stage": "watchdog", "ssot": "local-runtime", "costClass": "low", "disableSafe": False, "optional": False},
    "second-brain-safe-sync-watchdog": {"pipelineId": "runtime_watchdog", "stage": "watchdog", "ssot": "second-brain", "costClass": "low", "disableSafe": False, "optional": False},
    "morning-batch-followup-watchdog": {"pipelineId": "runtime_watchdog", "stage": "watchdog", "ssot": "physio-hermes-ops", "costClass": "low", "disableSafe": False, "optional": False},
    "rehab-research-pipeline-watchdog": {"pipelineId": "runtime_watchdog", "stage": "watchdog", "ssot": "physio-hermes-ops", "costClass": "low", "disableSafe": False, "optional": False},
    "kinelo-interview-dropzone-watchdog": {"pipelineId": "runtime_watchdog", "stage": "watchdog", "ssot": "physio-hermes-ops", "costClass": "low", "disableSafe": False, "optional": False},
    "ensure-kinelo-8888-server": {"pipelineId": "runtime_watchdog", "stage": "watchdog", "ssot": "physio-hermes-ops", "costClass": "low", "disableSafe": False, "optional": False},
    "calendar-auto-classify": {"pipelineId": "runtime_watchdog", "stage": "watchdog", "ssot": "local-runtime", "costClass": "low", "disableSafe": False, "optional": False},
    "notion-brain-candidate-exporter": {"pipelineId": "memory_review", "stage": "processing", "ssot": "second-brain", "costClass": "low", "disableSafe": False, "optional": False},
    "com.brain.ios-capture": {"pipelineId": "memory_capture", "stage": "capture", "ssot": "second-brain", "costClass": "low", "disableSafe": False, "optional": False},
    "com.youngkwon.secondbrain.mobile-note-delta": {"pipelineId": "memory_capture", "stage": "capture", "ssot": "second-brain", "costClass": "low", "disableSafe": False, "optional": False},
    "com.youngkwon.secondbrain.mobile-screenshot-delta": {"pipelineId": "memory_capture", "stage": "capture", "ssot": "second-brain", "costClass": "low", "disableSafe": False, "optional": False},
    "com.youngkwon.secondbrain.apple-notes-inbox-delta": {"pipelineId": "memory_capture", "stage": "capture", "ssot": "second-brain", "costClass": "low", "disableSafe": False, "optional": False},
    "com.youngkwon.secondbrain.google-keep-delta": {"pipelineId": "memory_capture", "stage": "capture", "ssot": "second-brain", "costClass": "low", "disableSafe": False, "optional": False},
    "com.youngkwon.chatgpt-capture.import-shares": {"pipelineId": "memory_capture", "stage": "capture", "ssot": "second-brain", "costClass": "low", "disableSafe": False, "optional": False},
    "com.youngkwon.secondbrain.codex-thread-delta": {"pipelineId": "memory_capture", "stage": "capture", "ssot": "second-brain", "costClass": "low", "disableSafe": False, "optional": False},
    "com.youngkwon.zotero-snapshot-sync": {"pipelineId": "research_literature_ingest", "stage": "capture", "ssot": "second-brain", "costClass": "low", "disableSafe": False, "optional": False},
    "ai.hermes.gateway-macbookbridge": {"pipelineId": "memory_capture", "stage": "watchdog", "ssot": "local-runtime", "costClass": "low", "disableSafe": False, "optional": False},
    "com.youngkwon.secondbrain.launchagent-health-snapshot": {"pipelineId": "runtime_watchdog", "stage": "watchdog", "ssot": "local-runtime", "costClass": "low", "disableSafe": False, "optional": False},
    "com.youngkwon.second-brain-safe-pull": {"pipelineId": "runtime_watchdog", "stage": "watchdog", "ssot": "second-brain", "costClass": "low", "disableSafe": False, "optional": False},
    "physio_app_overnight": {"pipelineId": "desktop_physio_app_ops", "stage": "processing", "ssot": "physio_app", "costClass": "medium", "disableSafe": False, "optional": False},
    "physio_app_orchestrator": {"pipelineId": "desktop_physio_app_ops", "stage": "processing", "ssot": "physio_app", "costClass": "medium", "disableSafe": False, "optional": False},
    "physio_app_orchestrator_retry": {"pipelineId": "desktop_physio_app_ops", "stage": "processing", "ssot": "physio_app", "costClass": "low", "disableSafe": False, "optional": False},
    "physio_app_smoke_core": {"pipelineId": "desktop_physio_app_ops", "stage": "watchdog", "ssot": "physio_app", "costClass": "low", "disableSafe": False, "optional": False},
    "physio_app_morning_report": {"pipelineId": "desktop_physio_app_ops", "stage": "delivery", "ssot": "physio_app", "costClass": "low", "disableSafe": False, "optional": False},
}

PHYSIO_APP_CRON_JOBS: tuple[dict[str, str], ...] = (
    {"runtime_id": "physio_app_overnight", "needle": "automation/run_overnight.sh", "label": "physio_app overnight batch"},
    {"runtime_id": "physio_app_orchestrator_retry", "needle": "automation/run_orchestrator_round.sh --retry", "label": "physio_app orchestrator retry"},
    {"runtime_id": "physio_app_orchestrator", "needle": "automation/run_orchestrator_round.sh", "label": "physio_app orchestrator round"},
    {"runtime_id": "physio_app_smoke_core", "needle": "automation/run_smoke_core.sh", "label": "physio_app smoke core"},
    {"runtime_id": "physio_app_morning_report", "needle": "automation/send_morning_report.sh", "label": "physio_app morning report"},
)


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except Exception:
        return None


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


def run_text(cmd: list[str]) -> str:
    return subprocess.run(cmd, check=True, text=True, capture_output=True).stdout


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def job_id(plane_id: str, runtime_id: str) -> str:
    return f"{plane_id}_{slug(runtime_id)}"


def codex_rrule_to_schedule(rrule: str) -> str:
    if not rrule:
        return "unknown"
    hour = re.search(r"BYHOUR=(\d+)", rrule)
    minute = re.search(r"BYMINUTE=(\d+)", rrule)
    day = re.search(r"BYDAY=([A-Z,]+)", rrule)
    hh = hour.group(1).zfill(2) if hour else "??"
    mm = minute.group(1).zfill(2) if minute else "??"
    if "FREQ=WEEKLY" in rrule and day:
        return f"weekly {day.group(1)} {hh}:{mm}"
    if "FREQ=DAILY" in rrule:
        return f"daily {hh}:{mm}"
    return rrule


def infer_health(enabled: bool, last_status: str | None, last_error: str | None) -> str:
    if not enabled:
        return "disabled"
    if last_error:
        return "failed"
    if last_status == "ok":
        return "healthy"
    if last_status in {"error", "failed"}:
        return "failed"
    return "running"


def build_job(
    plane_id: str,
    runtime_id: str,
    operator_label: str,
    schedule: str,
    enabled: bool,
    last_run_at: str | None,
    next_run_at: str | None,
    last_error: str | None,
    base_meta: dict[str, Any],
) -> dict[str, Any]:
    health = infer_health(enabled, base_meta.get("last_status"), last_error)
    return {
        "jobId": job_id(plane_id, runtime_id),
        "runtimeId": runtime_id,
        "operatorLabel": operator_label,
        "planeId": plane_id,
        "runtimeFamily": PLANE_META[plane_id]["runtimeFamily"],
        "pipelineId": base_meta["pipelineId"],
        "stage": base_meta["stage"],
        "owner": PLANE_META[plane_id]["owner"],
        "schedule": schedule,
        "enabled": enabled,
        "health": health,
        "input": base_meta.get("input", []),
        "output": base_meta.get("output", []),
        "ssot": base_meta["ssot"],
        "dependsOn": base_meta.get("dependsOn", []),
        "lastRunAt": last_run_at,
        "nextRunAt": next_run_at,
        "lastError": last_error,
        "costClass": base_meta["costClass"],
        "disableSafe": base_meta["disableSafe"],
        "optional": base_meta["optional"],
        "notes": base_meta.get("notes"),
    }


def load_hermes_jobs() -> list[dict[str, Any]]:
    jobs_payload = read_json(HERMES_HOME / "cron" / "jobs.json")
    out: list[dict[str, Any]] = []
    for item in jobs_payload.get("jobs", []):
        runtime_id = item.get("name") or item.get("id")
        if not runtime_id or runtime_id not in JOB_META:
            continue
        meta = dict(JOB_META[runtime_id])
        meta["last_status"] = item.get("last_status")
        schedule = item.get("schedule")
        if isinstance(schedule, dict):
            schedule = schedule.get("display") or schedule.get("expr") or str(schedule)
        out.append(
            build_job(
                plane_id="desktop_hermes",
                runtime_id=runtime_id,
                operator_label=runtime_id,
                schedule=str(schedule or "unknown"),
                enabled=bool(item.get("enabled")),
                last_run_at=item.get("last_run_at"),
                next_run_at=item.get("next_run_at"),
                last_error=item.get("last_error"),
                base_meta=meta,
            )
        )
    return out


def load_codex_jobs() -> list[dict[str, Any]]:
    if tomllib is None or not WINDOWS_CODEX_AUTOMATIONS_DIR.exists():
        return []
    out: list[dict[str, Any]] = []
    for path in sorted(WINDOWS_CODEX_AUTOMATIONS_DIR.glob("*/automation.toml")):
        data = tomllib.loads(path.read_text(encoding="utf-8"))
        runtime_id = data.get("id") or path.parent.name
        if runtime_id not in JOB_META:
            continue
        meta = dict(JOB_META[runtime_id])
        if data.get("status") == "ACTIVE":
            meta["last_status"] = "ok"
        out.append(
            build_job(
                plane_id="desktop_codex_automations",
                runtime_id=runtime_id,
                operator_label=data.get("name") or runtime_id,
                schedule=codex_rrule_to_schedule(data.get("rrule", "")),
                enabled=data.get("status") == "ACTIVE",
                last_run_at=None,
                next_run_at=None,
                last_error=None,
                base_meta=meta,
            )
        )
    return out


def load_physio_app_cron_jobs() -> list[dict[str, Any]]:
    try:
        crontab = run_text(["crontab", "-l"])
    except Exception:
        return []

    out: list[dict[str, Any]] = []
    for spec in PHYSIO_APP_CRON_JOBS:
        matched_line = next(
            (
                line.strip()
                for line in crontab.splitlines()
                if line.strip()
                and not line.strip().startswith("#")
                and spec["needle"] in line
            ),
            None,
        )
        if not matched_line:
            continue
        runtime_id = spec["runtime_id"]
        meta = dict(JOB_META[runtime_id])
        meta["last_status"] = "ok"
        schedule = " ".join(matched_line.split()[:5])
        out.append(
            build_job(
                plane_id="desktop_physio_app",
                runtime_id=runtime_id,
                operator_label=spec["label"],
                schedule=schedule,
                enabled=True,
                last_run_at=None,
                next_run_at=None,
                last_error=None,
                base_meta=meta,
            )
        )
    return out


def load_windows_scheduled_tasks() -> list[dict[str, Any]]:
    cmd = [
        "powershell.exe",
        "-NoProfile",
        "-Command",
        (
            "Get-ScheduledTask | "
            "Where-Object { $_.TaskName -match 'Hermes|WSL|Codex|Zotero|OpenClaw|Second|Brain' "
            "-or $_.TaskPath -match 'Hermes|WSL|Codex|Zotero|OpenClaw|Second|Brain' } | "
            "Select-Object TaskName,TaskPath,State | ConvertTo-Json -Compress"
        ),
    ]
    try:
        raw = run_text(cmd).strip()
    except Exception:
        return []
    if not raw:
        return []
    try:
        payload = json.loads(raw)
    except Exception:
        return []
    items = payload if isinstance(payload, list) else [payload]

    out: list[dict[str, Any]] = []
    for item in items:
        task_name = str(item.get("TaskName") or "").strip()
        if not task_name:
            continue
        task_path = str(item.get("TaskPath") or "\\")
        state = str(item.get("State") or "Unknown")
        enabled = state.lower() != "disabled"
        runtime_id = f"{task_path}{task_name}".replace("\\", "/").strip("/")
        meta = {
            "pipelineId": "windows_bootstrap",
            "stage": "watchdog",
            "ssot": "windows-task-scheduler",
            "costClass": "low",
            "disableSafe": False,
            "optional": False,
            "last_status": "ok" if state in {"Ready", "Running"} else None,
            "notes": f"Windows state: {state}",
        }
        out.append(
            build_job(
                plane_id="windows_scheduled_tasks",
                runtime_id=runtime_id,
                operator_label=task_name,
                schedule="windows task scheduler",
                enabled=enabled,
                last_run_at=None,
                next_run_at=None,
                last_error=None if enabled else f"state={state}",
                base_meta=meta,
            )
        )
    return out


def workflow_repo_label(path: Path) -> str:
    parts = path.parts
    if ".github" in parts:
        idx = parts.index(".github")
        if idx > 0:
            return parts[idx - 1]
    return path.parent.parent.name


def load_github_actions_jobs() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for workflow_dir in GITHUB_WORKFLOW_DIRS:
        if not workflow_dir.exists():
            continue
        repo = workflow_repo_label(workflow_dir)
        for path in sorted(workflow_dir.glob("*")):
            if path.suffix not in {".yml", ".yaml"}:
                continue
            runtime_id = f"{repo}/{path.name}"
            meta = {
                "pipelineId": "github_ci_cd",
                "stage": "watchdog",
                "ssot": "github",
                "costClass": "medium",
                "disableSafe": False,
                "optional": False,
                "last_status": "ok",
                "notes": str(path),
            }
            out.append(
                build_job(
                    plane_id="github_actions",
                    runtime_id=runtime_id,
                    operator_label=f"{repo}: {path.stem}",
                    schedule="workflow definition",
                    enabled=True,
                    last_run_at=None,
                    next_run_at=None,
                    last_error=None,
                    base_meta=meta,
                )
            )
    return out


def launchagent_health(item: dict[str, Any]) -> str:
    if not item.get("exists"):
        return "disabled"
    if item.get("loaded") and item.get("last_exit_status") in {None, 0}:
        return "healthy"
    if item.get("loaded") and item.get("last_exit_status") not in {None, 0}:
        return "failed"
    if item.get("loaded"):
        return "running"
    return "disabled"


def load_launchagent_jobs() -> list[dict[str, Any]]:
    payload = read_json(MACBOOK_LAUNCHAGENT_SNAPSHOT_PATH)
    out: list[dict[str, Any]] = []
    for item in payload.get("items", []):
        runtime_id = item.get("label")
        if not runtime_id or runtime_id not in JOB_META:
            continue
        meta = dict(JOB_META[runtime_id])
        health = launchagent_health(item)
        out.append(
            {
                "jobId": job_id("macbook_launchagents", runtime_id),
                "runtimeId": runtime_id,
                "operatorLabel": item.get("display_name") or runtime_id,
                "planeId": "macbook_launchagents",
                "runtimeFamily": PLANE_META["macbook_launchagents"]["runtimeFamily"],
                "pipelineId": meta["pipelineId"],
                "stage": meta["stage"],
                "owner": PLANE_META["macbook_launchagents"]["owner"],
                "schedule": item.get("schedule") or "unknown",
                "enabled": bool(item.get("exists")),
                "health": health,
                "input": meta.get("input", []),
                "output": meta.get("output", []),
                "ssot": meta["ssot"],
                "dependsOn": meta.get("dependsOn", []),
                "lastRunAt": payload.get("generated_at"),
                "nextRunAt": None,
                "lastError": None if item.get("last_exit_status") in {None, 0} else f"exit_status={item.get('last_exit_status')}",
                "costClass": meta["costClass"],
                "disableSafe": meta["disableSafe"],
                "optional": meta["optional"],
                "notes": item.get("role"),
            }
        )
    return out


def build_pipelines(jobs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for job in jobs:
        grouped.setdefault(job["pipelineId"], []).append(job)
    out: list[dict[str, Any]] = []
    for pipeline_id, items in grouped.items():
        meta = PIPELINE_META[pipeline_id]
        enabled_items = [job for job in items if job["enabled"]]
        failed = any(job["health"] == "failed" for job in enabled_items)
        delayed = any(job["health"] == "delayed" for job in enabled_items)
        if failed:
            health = "failed"
        elif delayed:
            health = "delayed"
        elif enabled_items:
            health = "healthy"
        else:
            health = "disabled"
        next_runs = sorted(dt for dt in (parse_iso(job["nextRunAt"]) for job in enabled_items) if dt)
        last_success = sorted(
            dt for dt in (
                parse_iso(job["lastRunAt"]) if job["health"] == "healthy" else None for job in enabled_items
            ) if dt
        )
        out.append({
            "pipelineId": pipeline_id,
            "name": meta["name"],
            "description": meta["description"],
            "owner": PLANE_META[meta["primaryPlaneId"]]["owner"],
            "primaryPlaneId": meta["primaryPlaneId"],
            "stage": meta["stage"],
            "stages": meta["stages"],
            "input": meta["input"],
            "output": meta["output"],
            "ssot": meta["ssot"],
            "dependsOn": sorted({dep for job in items for dep in job.get("dependsOn", [])}),
            "jobIds": [job["jobId"] for job in items],
            "health": health,
            "impactClass": meta["impactClass"],
            "lastSuccessAt": last_success[-1].isoformat() if last_success else None,
            "nextRunAt": next_runs[0].isoformat() if next_runs else None,
            "disableSafe": meta["disableSafe"],
        })
    return sorted(out, key=lambda item: item["pipelineId"])


def build_planes(jobs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for plane_id, meta in PLANE_META.items():
        items = [job for job in jobs if job["planeId"] == plane_id]
        if any(job["health"] == "failed" for job in items):
            health = "failed"
        elif any(job["health"] == "delayed" for job in items):
            health = "delayed"
        elif items:
            health = "healthy"
        else:
            health = "unknown"
        out.append({
            "planeId": plane_id,
            "name": meta["name"],
            "host": meta["host"],
            "runtimeFamily": meta["runtimeFamily"],
            "owner": meta["owner"],
            "jobCount": len(items),
            "runningCount": sum(1 for job in items if job["enabled"]),
            "healthyCount": sum(1 for job in items if job["health"] == "healthy"),
            "delayedCount": sum(1 for job in items if job["health"] == "delayed"),
            "failedCount": sum(1 for job in items if job["health"] == "failed"),
            "pausedCount": sum(1 for job in items if job["health"] == "paused"),
            "disabledCount": sum(1 for job in items if job["health"] == "disabled"),
            "lastHeartbeatAt": now_iso(),
            "health": health,
        })
    return out


def build_failures(jobs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    for job in jobs:
        if job["health"] != "failed":
            continue
        failures.append({
            "failureId": f"{job['jobId']}_{slug(job.get('lastRunAt') or now_iso())}",
            "jobId": job["jobId"],
            "pipelineId": job["pipelineId"],
            "planeId": job["planeId"],
            "detectedAt": job.get("lastRunAt") or now_iso(),
            "health": "failed",
            "impactClass": next((p["impactClass"] for p in build_pipelines([job]) if p["pipelineId"] == job["pipelineId"]), "medium"),
            "summary": job.get("lastError") or "job reported failure",
            "source": job["runtimeId"],
            "recommendedAction": f"inspect {job['runtimeId']}",
        })
    return failures


def build_sources() -> list[dict[str, Any]]:
    return [
        {
            "sourceId": "desktop_hermes_runtime_jobs",
            "type": "json",
            "path": str(HERMES_HOME / "cron" / "jobs.json"),
            "planeId": "desktop_hermes",
            "lastObservedAt": now_iso(),
        },
        {
            "sourceId": "desktop_hermes_runtime_health",
            "type": "json",
            "path": str(DERIVED_DIR / "runtime_health_snapshot.json"),
            "planeId": "desktop_hermes",
            "lastObservedAt": now_iso(),
        },
        {
            "sourceId": "macbook_launchagent_snapshot",
            "type": "json",
            "path": str(MACBOOK_LAUNCHAGENT_SNAPSHOT_PATH),
            "planeId": "macbook_launchagents",
            "lastObservedAt": now_iso(),
        },
        {
            "sourceId": "desktop_codex_automations",
            "type": "toml",
            "path": str(WINDOWS_CODEX_AUTOMATIONS_DIR),
            "planeId": "desktop_codex_automations",
            "lastObservedAt": now_iso(),
        },
        {
            "sourceId": "desktop_physio_app_crontab",
            "type": "crontab",
            "path": "crontab -l",
            "planeId": "desktop_physio_app",
            "lastObservedAt": now_iso(),
        },
        {
            "sourceId": "windows_scheduled_tasks",
            "type": "windows-task-scheduler",
            "path": "Get-ScheduledTask",
            "planeId": "windows_scheduled_tasks",
            "lastObservedAt": now_iso(),
        },
        {
            "sourceId": "github_workflow_definitions",
            "type": "filesystem",
            "path": ", ".join(str(path) for path in GITHUB_WORKFLOW_DIRS),
            "planeId": "github_actions",
            "lastObservedAt": now_iso(),
        },
    ]


def build_summary(jobs: list[dict[str, Any]]) -> dict[str, Any]:
    next_candidates = []
    for job in jobs:
        dt = parse_iso(job.get("nextRunAt"))
        if dt:
            next_candidates.append((dt, job))
    next_candidates.sort(key=lambda pair: pair[0])
    next_run = None
    if next_candidates:
        dt, job = next_candidates[0]
        next_run = {
            "jobId": job["jobId"],
            "operatorLabel": job["operatorLabel"],
            "planeId": job["planeId"],
            "pipelineId": job["pipelineId"],
            "scheduledAt": dt.isoformat(),
        }
    return {
        "running": sum(1 for job in jobs if job["enabled"]),
        "healthy": sum(1 for job in jobs if job["health"] == "healthy"),
        "delayed": sum(1 for job in jobs if job["health"] == "delayed"),
        "failed": sum(1 for job in jobs if job["health"] == "failed"),
        "paused": sum(1 for job in jobs if job["health"] == "paused"),
        "disabled": sum(1 for job in jobs if job["health"] == "disabled"),
        "todayRuns": sum(1 for job in jobs if job.get("lastRunAt")),
        "todaySuccess": sum(1 for job in jobs if job["health"] == "healthy" and job.get("lastRunAt")),
        "todayFailure": sum(1 for job in jobs if job["health"] == "failed" and job.get("lastRunAt")),
        "nextRun": next_run,
    }


def main() -> None:
    jobs = (
        load_hermes_jobs()
        + load_launchagent_jobs()
        + load_codex_jobs()
        + load_physio_app_cron_jobs()
        + load_windows_scheduled_tasks()
        + load_github_actions_jobs()
    )
    pipelines = build_pipelines(jobs)
    failures = build_failures(jobs)
    payload = {
        "schemaVersion": "automation-control-center-read-model-v1",
        "generatedAt": now_iso(),
        "workspace": "youngkwon-ops",
        "summary": build_summary(jobs),
        "planes": build_planes(jobs),
        "pipelines": pipelines,
        "jobs": sorted(jobs, key=lambda item: (item["planeId"], item["runtimeId"])),
        "failures": failures,
        "sources": build_sources(),
    }
    write_json(OUT_PATH, payload)
    print(str(OUT_PATH))


if __name__ == "__main__":
    main()
