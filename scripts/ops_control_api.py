#!/usr/bin/env python3
import json
import os
import re
import subprocess
import time
import uuid
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Lock
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
HOST = os.getenv("OPS_CTL_HOST", "127.0.0.1")
PORT = int(os.getenv("OPS_CTL_PORT", "8788"))
TOKEN = os.getenv("OPS_CTL_TOKEN", "")
READ_TOKEN = os.getenv("OPS_CTL_READ_TOKEN", TOKEN)
EXEC_TOKEN = os.getenv("OPS_CTL_EXEC_TOKEN", TOKEN)
EXEC_ADMIN_TOKEN = os.getenv("OPS_CTL_EXEC_ADMIN_TOKEN", EXEC_TOKEN)
EXEC_OPERATOR_TOKEN = os.getenv("OPS_CTL_EXEC_OPERATOR_TOKEN", "")
REQUIRE_TOKEN = os.getenv("OPS_CTL_REQUIRE_TOKEN", "1") == "1"
AUDIT_LOG = Path(os.getenv("OPS_CTL_AUDIT_LOG", str(ROOT / "lineage" / "actions_audit.jsonl")))
LOCK_PATH = Path(os.getenv("OPS_CTL_LOCK_FILE", str(ROOT / ".runtime" / "ops_control.lock")))
HANDOFF_NOTIFY_LOG = Path(
    os.getenv("OPS_CTL_HANDOFF_NOTIFY_LOG", str(ROOT / "lineage" / "continuity_handoff_notifications.jsonl"))
)
MISSION_CONTROL_STATE_DIR = Path(
    os.getenv(
        "OPS_CTL_STATE_DIR",
        os.getenv(
            "HERMES_MISSION_CONTROL_STATE_DIR",
            str(Path.home() / ".local" / "state" / "physio-hermes-ops" / "mission_control"),
        ),
    )
)
LEGACY_HANDOFF_INBOX_PATH = ROOT / ".runtime" / "mission_control" / "handoff_inbox.json"
HANDOFF_INBOX_PATH = Path(
    os.getenv(
        "OPS_CTL_HANDOFF_INBOX_PATH",
        os.getenv("HERMES_MISSION_CONTROL_HANDOFF_INBOX_PATH", str(MISSION_CONTROL_STATE_DIR / "handoff_inbox.json")),
    )
)
MAX_RETRIES = max(1, int(os.getenv("OPS_CTL_MAX_RETRIES", "2")))
RETRY_DELAY = float(os.getenv("OPS_CTL_RETRY_DELAY_SEC", "1.0"))
KNOWLEDGE_DIR = Path(os.getenv("OPS_KNOWLEDGE_DIR", str(ROOT / "ops_knowledge")))
KNOWLEDGE_AUTOGIT = os.getenv("OPS_KNOWLEDGE_AUTOGIT", "0") == "1"

COMMANDS = {
    "refresh": [["python3", "scripts/export_cron_status.py"]],
    "pause_all": [
        ["hermes", "cron", "pause", "61fbb6fbc580"],
        ["hermes", "cron", "pause", "3320eb412834"],
        ["hermes", "cron", "pause", "8d13ba66655d"],
        ["hermes", "cron", "pause", "b96d745a16c9"],
        ["hermes", "cron", "pause", "9f39d5d4dd0a"],
        ["hermes", "cron", "pause", "22e0930cff69"],
        ["hermes", "cron", "pause", "4fa36ebb15d2"],
        ["python3", "scripts/export_cron_status.py"],
    ],
    "resume_core": [
        ["hermes", "cron", "resume", "61fbb6fbc580"],
        ["hermes", "cron", "resume", "3320eb412834"],
        ["hermes", "cron", "resume", "8d13ba66655d"],
        ["hermes", "cron", "resume", "b96d745a16c9"],
        ["hermes", "cron", "resume", "9f39d5d4dd0a"],
        ["python3", "scripts/export_cron_status.py"],
    ],
    "finalize_once": [
        ["hermes", "cron", "run", "4fa36ebb15d2"],
        ["hermes", "cron", "pause", "4fa36ebb15d2"],
        ["python3", "scripts/export_cron_status.py"],
    ],
}

RUNTIME_LOCK = Lock()
ROLE_ACTIONS = {
    "admin": set(COMMANDS.keys()),
    "operator": {"refresh"},
}


def now():
    return datetime.now().isoformat(timespec="seconds")


def today():
    return datetime.now().strftime("%Y-%m-%d")


def slug(s: str):
    return re.sub(r"[^a-zA-Z0-9._-]+", "-", s).strip("-").lower()[:80] or "note"


def _ensure_parent(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)


def read_json(path: Path, default=None):
    if default is None:
        default = {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def read_jsonl(path: Path):
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except Exception:
            continue
    return out


def write_json(path: Path, payload):
    _ensure_parent(path)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def audit(entry: dict):
    _ensure_parent(AUDIT_LOG)
    with AUDIT_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def append_jsonl(path: Path, entry: dict):
    _ensure_parent(path)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def compact_text(value, limit=500):
    text = str(value or "").strip().replace("\n", " ")
    if not text:
        return None
    return text if len(text) <= limit else text[: limit - 1] + "…"


def append_markdown(path: Path, text: str):
    _ensure_parent(path)
    with path.open("a", encoding="utf-8") as f:
        f.write(text)


def save_markdown(path: Path, text: str):
    _ensure_parent(path)
    path.write_text(text, encoding="utf-8")


def knowledge_note_path(kind: str, title: str):
    base = KNOWLEDGE_DIR / "00_raw" / today()
    return base / f"{datetime.now().strftime('%H%M%S')}-{slug(kind)}-{slug(title)}.md"


def knowledge_wiki_path(kind: str, title: str):
    base = KNOWLEDGE_DIR / "10_wiki" / "decisions"
    return base / f"{today()}-{slug(kind)}-{slug(title)}.md"


def latest_events(limit=200):
    rows = read_jsonl(ROOT / "lineage" / "events.jsonl")
    return rows[-limit:]


def summarize_mode_recommendation():
    events = latest_events(80)
    recent = events[-12:]
    fail_n = sum(1 for e in recent if str(e.get("status", "")).upper() == "FAIL")
    check_n = sum(1 for e in recent if str(e.get("status", "")).upper() == "CHECK")
    gen = read_json(ROOT / "lineage" / "generation_cycle_state.json", {})
    hb = read_json(ROOT / "lineage" / "heartbeat.json", {})
    decision = str(gen.get("decision", "UNKNOWN")).upper()
    alive = bool(hb.get("alive", True))

    if (not alive) or fail_n > 0 or decision == "RED":
        return {"mode": "SAFE", "reason": f"alive={alive}, decision={decision}, fail={fail_n}"}
    if check_n > 0 or decision == "YELLOW":
        return {"mode": "NORMAL", "reason": f"decision={decision}, check={check_n}"}
    return {"mode": "AGGRESSIVE", "reason": f"decision={decision}, fail={fail_n}, check={check_n}"}


def compute_fsm_state():
    hb = read_json(ROOT / "lineage" / "heartbeat.json", {})
    gen = read_json(ROOT / "lineage" / "generation_cycle_state.json", {})
    spawn = read_json(ROOT / "lineage" / "spawn_state.json", {})
    dispatch = read_json(ROOT / "lineage" / "dispatch_state.json", {})
    events = latest_events(50)
    recent = events[-12:]

    fail_n = sum(1 for e in recent if str(e.get("status", "")).upper() == "FAIL")
    check_n = sum(1 for e in recent if str(e.get("status", "")).upper() == "CHECK")
    alive = bool(hb.get("alive", True))
    decision = str(gen.get("decision", "UNKNOWN")).upper()
    sp = str(spawn.get("state", "unknown")).lower()
    dp = str(dispatch.get("state", "unknown")).lower()

    if not alive:
        state = "HALTED"
        reason = "heartbeat down"
    elif fail_n > 0 or decision == "RED":
        state = "DEGRADED"
        reason = f"decision={decision}, fail={fail_n}"
    elif check_n > 0 or decision == "YELLOW":
        state = "CAUTION"
        reason = f"decision={decision}, check={check_n}"
    elif sp == "scheduled" and dp == "scheduled":
        state = "RUNNING"
        reason = "spawn/dispatch scheduled"
    else:
        state = "IDLE"
        reason = f"spawn={sp}, dispatch={dp}"

    return {
        "state": state,
        "reason": reason,
        "signals": {
            "heartbeat_alive": alive,
            "generation_decision": decision,
            "recent_fail": fail_n,
            "recent_check": check_n,
            "spawn_state": sp,
            "dispatch_state": dp,
        },
    }


def build_fsm_snapshot(limit=30):
    rows = read_recent_audits(max(80, limit * 3))
    transitions = []
    prev = None
    for r in sorted(rows, key=lambda x: x.get("time", "")):
        action = str(r.get("action", ""))
        ok = bool(r.get("ok", False))
        if action == "pause_all" and ok:
            nxt, evt = "IDLE", "pause_all_ok"
        elif action == "resume_core" and ok:
            nxt, evt = "RUNNING", "resume_core_ok"
        elif action == "finalize_once" and ok:
            nxt, evt = "CAUTION", "finalize_once_ok"
        elif action == "refresh" and ok:
            nxt, evt = None, "refresh_ok"
        else:
            continue

        if nxt is None:
            continue
        frm = prev or "UNKNOWN"
        transitions.append({"time": r.get("time", "-"), "event": evt, "from": frm, "to": nxt})
        prev = nxt

    current = compute_fsm_state()
    fsm_def = {
        "states": ["HALTED", "DEGRADED", "CAUTION", "RUNNING", "IDLE"],
        "transitions": [
            {"event": "heartbeat_down", "from": "*", "to": "HALTED"},
            {"event": "decision_red_or_fail", "from": "*", "to": "DEGRADED"},
            {"event": "decision_yellow_or_check", "from": "*", "to": "CAUTION"},
            {"event": "resume_core_ok", "from": "IDLE|CAUTION", "to": "RUNNING"},
            {"event": "pause_all_ok", "from": "RUNNING|CAUTION", "to": "IDLE"},
        ],
    }
    return {"ok": True, "current": current, "recent_transitions": list(reversed(transitions[-limit:])), "definition": fsm_def}


def harvest_lineage_knowledge(trigger_action: str, role: str):
    events = latest_events(50)
    risky = [e for e in events if str(e.get("status", "")).upper() in {"FAIL", "CHECK"}]
    risky_recent = risky[-5:]
    gen = read_json(ROOT / "lineage" / "generation_cycle_state.json", {})
    recommendation = summarize_mode_recommendation()

    title = f"{trigger_action}-{recommendation['mode']}"
    raw_path = knowledge_note_path("lineage", title)
    wiki_path = knowledge_wiki_path("lineage", title)

    body_lines = [
        f"# Ops lineage snapshot",
        f"- time: {now()}",
        f"- trigger_action: {trigger_action}",
        f"- role: {role}",
        f"- mode_recommendation: {recommendation['mode']}",
        f"- reason: {recommendation['reason']}",
        f"- generation_decision: {gen.get('decision', '-')}",
        "",
        "## recent FAIL/CHECK",
    ]
    if not risky_recent:
        body_lines.append("- none")
    else:
        for e in risky_recent:
            body_lines.append(
                f"- {e.get('timestamp') or e.get('ts') or '-'} | {e.get('wave_id','-')} | {e.get('profile_id','-')} | {e.get('status','-')} | {e.get('notes') or e.get('summary') or '-'}"
            )

    raw_md = "\n".join(body_lines) + "\n"
    save_markdown(raw_path, raw_md)

    wiki_md = "\n".join([
        f"# Decision: {recommendation['mode']}",
        f"- date: {today()}",
        f"- source: lineage snapshot",
        f"- trigger_action: {trigger_action}",
        f"- role: {role}",
        f"- recommendation: {recommendation['mode']}",
        f"- reason: {recommendation['reason']}",
        "",
        "## Next action guide",
        "- SAFE: refresh only, pause 유지",
        "- NORMAL: resume_core 제한 실행",
        "- AGGRESSIVE: finalize_once 포함 가능",
        "",
        f"## Linked raw\n- {raw_path.relative_to(ROOT)}",
        "",
    ])
    save_markdown(wiki_path, wiki_md)

    return {
        "raw_path": str(raw_path.relative_to(ROOT)),
        "wiki_path": str(wiki_path.relative_to(ROOT)),
        "mode": recommendation["mode"],
    }


def safe_autogit(paths, message):
    if not KNOWLEDGE_AUTOGIT:
        return {"enabled": False}

    allowed_roots = [ROOT / "ops_knowledge", ROOT / "docs" / "runbook"]
    abs_paths = [ROOT / p if not Path(p).is_absolute() else Path(p) for p in paths]
    for p in abs_paths:
        if not any(str(p.resolve()).startswith(str(r.resolve())) for r in allowed_roots):
            return {"enabled": True, "ok": False, "error": f"path_not_allowed: {p}"}

    cmds = [
        ["git", "add", *[str(Path(p).as_posix()) for p in paths]],
        ["git", "commit", "-m", message],
        ["git", "push", "origin", "main"],
    ]
    results = []
    for c in cmds:
        p = subprocess.run(c, cwd=ROOT, text=True, capture_output=True)
        results.append({"cmd": " ".join(c), "exit_code": p.returncode, "stdout": p.stdout[-2000:], "stderr": p.stderr[-2000:]})
        if p.returncode != 0 and "nothing to commit" not in (p.stdout + p.stderr).lower():
            return {"enabled": True, "ok": False, "results": results}
    return {"enabled": True, "ok": True, "results": results}


def run_cmd(cmd, timeout_sec=180):
    attempts = []
    for n in range(1, MAX_RETRIES + 1):
        p = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, timeout=timeout_sec)
        rec = {
            "attempt": n,
            "exit_code": p.returncode,
            "stdout": (p.stdout or "")[-4000:],
            "stderr": (p.stderr or "")[-4000:],
        }
        attempts.append(rec)
        if p.returncode == 0:
            break
        if n < MAX_RETRIES:
            time.sleep(RETRY_DELAY)

    last = attempts[-1]
    return {
        "cmd": " ".join(cmd),
        "exit_code": last["exit_code"],
        "stdout": last["stdout"],
        "stderr": last["stderr"],
        "attempts": attempts,
    }


def read_recent_audits(limit=20):
    if not AUDIT_LOG.exists():
        return []
    rows = AUDIT_LOG.read_text(encoding="utf-8").splitlines()
    out = []
    for line in rows[-limit:]:
        try:
            out.append(json.loads(line))
        except Exception:
            continue
    return list(reversed(out))


def read_recent_knowledge(limit=20):
    files = sorted((KNOWLEDGE_DIR / "00_raw").glob("**/*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
    out = []
    for p in files[:limit]:
        try:
            lines = p.read_text(encoding="utf-8").splitlines()
            head = next((ln for ln in lines if ln.startswith("- trigger_action:")), "")
            out.append({
                "path": str(p.relative_to(ROOT)),
                "updated_at": datetime.fromtimestamp(p.stat().st_mtime).isoformat(timespec="seconds"),
                "trigger": head.replace("- trigger_action:", "").strip() if head else "-",
            })
        except Exception:
            continue
    return out


def build_knowledge_graph(limit=50):
    nodes, edges = [], []
    seen = set()

    def add_node(node_id, label, ntype):
        if node_id in seen:
            return
        seen.add(node_id)
        nodes.append({"id": node_id, "label": label, "type": ntype})

    recent_notes = read_recent_knowledge(limit)
    for n in recent_notes:
        note_id = f"note:{n['path']}"
        add_node(note_id, n["path"].split("/")[-1], "knowledge")
        trig = f"action:{n.get('trigger','-')}"
        add_node(trig, n.get("trigger", "-"), "action")
        edges.append({"from": trig, "to": note_id, "type": "creates"})

    for a in read_recent_audits(40):
        aid = f"audit:{a.get('time','-')}:{a.get('action','-')}"
        add_node(aid, f"{a.get('action','-')}@{a.get('time','-')}", "audit")
        action = f"action:{a.get('action','-')}"
        add_node(action, a.get("action", "-"), "action")
        edges.append({"from": action, "to": aid, "type": "logs"})

    return {"ok": True, "nodes": nodes[:200], "edges": edges[:300]}


HANDOFF_STATUSES = {"waiting_for_codex", "in_progress", "needs_reply", "done", "blocked"}
MISSION_ITEM_STATUSES = {"backlog", "ready", "assigned", "in_progress", "needs_review", "blocked", "done"}
MISSION_ACTION_STATUSES = {"queued", "running", "done", "failed", "blocked", "cancelled"}
MISSION_ACTION_TYPES = {"desktop_hermes_prompt", "desktop_repo_sync_restart_smoke"}


def base_handoff_inbox_state():
    return {
        "version": 1,
        "updatedAt": now(),
        "handoffsByOrg": {},
        "plansByOrg": {},
        "tasksByOrg": {},
        "actionsByOrg": {},
    }


def load_handoff_inbox_state():
    state = read_json(HANDOFF_INBOX_PATH, base_handoff_inbox_state()) if HANDOFF_INBOX_PATH.exists() else None
    if state is None and HANDOFF_INBOX_PATH != LEGACY_HANDOFF_INBOX_PATH:
        legacy_state = read_json(LEGACY_HANDOFF_INBOX_PATH, None)
        if isinstance(legacy_state, dict):
            state = legacy_state
            write_json(HANDOFF_INBOX_PATH, state)
    if not isinstance(state, dict):
        return base_handoff_inbox_state()
    if not isinstance(state.get("handoffsByOrg"), dict):
        state["handoffsByOrg"] = {}
    if not isinstance(state.get("plansByOrg"), dict):
        state["plansByOrg"] = {}
    if not isinstance(state.get("tasksByOrg"), dict):
        state["tasksByOrg"] = {}
    if not isinstance(state.get("actionsByOrg"), dict):
        state["actionsByOrg"] = {}
    return state


def save_handoff_inbox_state(state):
    state["updatedAt"] = now()
    write_json(HANDOFF_INBOX_PATH, state)


def normalized_handoff_status(value, default="waiting_for_codex"):
    status = str(value or "").strip()
    return status if status in HANDOFF_STATUSES else default


def normalized_mission_item_status(value, default="backlog"):
    status = str(value or "").strip()
    return status if status in MISSION_ITEM_STATUSES else default


def normalized_mission_action_status(value, default="queued"):
    status = str(value or "").strip()
    return status if status in MISSION_ACTION_STATUSES else default


def normalized_priority(value, default=50):
    try:
        priority = int(value)
    except Exception:
        priority = default
    return max(0, min(100, priority))


def handoff_party(value, default_agent, default_surface):
    row = value if isinstance(value, dict) else {}
    return {
        "agent": str(row.get("agent") or default_agent).strip() or default_agent,
        "surface": str(row.get("surface") or default_surface).strip() or default_surface,
        "host": str(row.get("host") or "").strip() or None,
    }


def handoff_source_thread(value):
    row = value if isinstance(value, dict) else {}
    return {
        "channelId": str(row.get("channelId") or "").strip() or None,
        "threadId": str(row.get("threadId") or "").strip() or None,
        "channelName": str(row.get("channelName") or "").strip() or None,
        "threadName": str(row.get("threadName") or "").strip() or None,
        "url": str(row.get("url") or "").strip() or None,
    }


def create_handoff_item(payload):
    organization_id = str(payload.get("organizationId") or "").strip()
    if not organization_id:
        raise ValueError("organizationId is required")

    goal = str(payload.get("goal") or "").strip()
    if not goal:
        raise ValueError("goal is required")

    handoff_id = str(payload.get("id") or payload.get("handoffId") or f"handoff-{uuid.uuid4()}").strip()
    timestamp = now()
    return organization_id, {
        "id": handoff_id,
        "kind": str(payload.get("kind") or "handoff_request").strip() or "handoff_request",
        "status": normalized_handoff_status(payload.get("status")),
        "createdAt": str(payload.get("createdAt") or timestamp).strip() or timestamp,
        "updatedAt": timestamp,
        "from": handoff_party(payload.get("from"), "desktop-hermes", "discord"),
        "to": handoff_party(payload.get("to"), "macbook-codex", "codex-app"),
        "repo": str(payload.get("repo") or "").strip() or None,
        "goal": compact_text(goal, 500),
        "context": compact_text(payload.get("context"), 1200),
        "expectedOutput": compact_text(payload.get("expectedOutput") or payload.get("expected_output"), 800),
        "sourceThread": handoff_source_thread(payload.get("sourceThread") or payload.get("source_thread")),
        "result": compact_text(payload.get("result"), 1200),
        "linkedRunId": str(payload.get("linkedRunId") or payload.get("runId") or "").strip() or None,
        "linkedConversationId": str(payload.get("linkedConversationId") or payload.get("conversationId") or "").strip() or None,
        "tags": [str(item).strip() for item in payload.get("tags", []) if str(item).strip()] if isinstance(payload.get("tags"), list) else [],
    }


def list_handoff_items(organization_id, limit=20, status=None):
    state = load_handoff_inbox_state()
    rows = state.get("handoffsByOrg", {}).get(organization_id, [])
    if not isinstance(rows, list):
        return []
    items = [row for row in rows if isinstance(row, dict)]
    if status:
        items = [item for item in items if item.get("status") == status]
    items.sort(key=lambda item: str(item.get("updatedAt") or item.get("createdAt") or ""), reverse=True)
    return items[: max(1, limit)]


def update_handoff_status(payload, handoff_id):
    organization_id = str(payload.get("organizationId") or "").strip()
    if not organization_id:
        raise ValueError("organizationId is required")
    next_status = normalized_handoff_status(payload.get("status"), default="")
    if not next_status:
        raise ValueError("valid status is required")

    state = load_handoff_inbox_state()
    rows = state.setdefault("handoffsByOrg", {}).setdefault(organization_id, [])
    if not isinstance(rows, list):
        rows = []
        state["handoffsByOrg"][organization_id] = rows

    for index, item in enumerate(rows):
        if not isinstance(item, dict) or str(item.get("id") or "") != handoff_id:
            continue
        updated = {**item, "status": next_status, "updatedAt": now()}
        if "result" in payload:
            updated["result"] = compact_text(payload.get("result"), 1200)
        rows[index] = updated
        save_handoff_inbox_state(state)
        return organization_id, updated

    raise KeyError("Handoff not found")


def mission_source_thread(value):
    return handoff_source_thread(value)


def create_plan_item(payload):
    organization_id = str(payload.get("organizationId") or "").strip()
    if not organization_id:
        raise ValueError("organizationId is required")

    title = str(payload.get("title") or payload.get("goal") or "").strip()
    if not title:
        raise ValueError("title is required")

    timestamp = now()
    plan_id = str(payload.get("id") or payload.get("planId") or f"plan-{uuid.uuid4()}").strip()
    return organization_id, {
        "id": plan_id,
        "kind": "plan",
        "status": normalized_mission_item_status(payload.get("status"), default="backlog"),
        "createdAt": str(payload.get("createdAt") or timestamp).strip() or timestamp,
        "updatedAt": timestamp,
        "title": compact_text(title, 300),
        "horizon": str(payload.get("horizon") or "long").strip() or "long",
        "summary": compact_text(payload.get("summary") or payload.get("context"), 1200),
        "owner": handoff_party(payload.get("owner"), "youngkwon", "operator"),
        "sourceThread": mission_source_thread(payload.get("sourceThread") or payload.get("source_thread")),
        "priority": normalized_priority(payload.get("priority"), default=50),
        "result": compact_text(payload.get("result"), 1200),
        "tags": [str(item).strip() for item in payload.get("tags", []) if str(item).strip()] if isinstance(payload.get("tags"), list) else [],
    }


def create_task_item(payload):
    organization_id = str(payload.get("organizationId") or "").strip()
    if not organization_id:
        raise ValueError("organizationId is required")

    title = str(payload.get("title") or payload.get("goal") or "").strip()
    if not title:
        raise ValueError("title is required")

    timestamp = now()
    task_id = str(payload.get("id") or payload.get("taskId") or f"task-{uuid.uuid4()}").strip()
    return organization_id, {
        "id": task_id,
        "kind": "task",
        "status": normalized_mission_item_status(payload.get("status"), default="ready"),
        "createdAt": str(payload.get("createdAt") or timestamp).strip() or timestamp,
        "updatedAt": timestamp,
        "planId": str(payload.get("planId") or "").strip() or None,
        "title": compact_text(title, 300),
        "context": compact_text(payload.get("context"), 1200),
        "expectedOutput": compact_text(payload.get("expectedOutput") or payload.get("expected_output"), 800),
        "assignee": handoff_party(payload.get("assignee") or payload.get("to"), "macbook-codex", "codex-app"),
        "repo": str(payload.get("repo") or "").strip() or None,
        "sourceThread": mission_source_thread(payload.get("sourceThread") or payload.get("source_thread")),
        "priority": normalized_priority(payload.get("priority"), default=50),
        "result": compact_text(payload.get("result"), 1200),
        "linkedHandoffId": str(payload.get("linkedHandoffId") or payload.get("handoffId") or "").strip() or None,
        "tags": [str(item).strip() for item in payload.get("tags", []) if str(item).strip()] if isinstance(payload.get("tags"), list) else [],
    }


def mission_action_target(value):
    return handoff_party(value, "desktop-hermes", "hermes-gateway")


def create_mission_action_item(payload):
    organization_id = str(payload.get("organizationId") or "").strip()
    if not organization_id:
        raise ValueError("organizationId is required")

    action_type = str(payload.get("actionType") or payload.get("type") or "").strip()
    if action_type not in MISSION_ACTION_TYPES:
        raise ValueError(f"valid actionType is required: {', '.join(sorted(MISSION_ACTION_TYPES))}")

    title = str(payload.get("title") or payload.get("goal") or action_type).strip()
    timestamp = now()
    action_id = str(payload.get("id") or payload.get("actionId") or f"action-{uuid.uuid4()}").strip()
    params = payload.get("params") if isinstance(payload.get("params"), dict) else {}
    return organization_id, {
        "id": action_id,
        "kind": "mission_action",
        "status": normalized_mission_action_status(payload.get("status"), default="queued"),
        "actionType": action_type,
        "createdAt": str(payload.get("createdAt") or timestamp).strip() or timestamp,
        "updatedAt": timestamp,
        "startedAt": None,
        "finishedAt": None,
        "attempts": 0,
        "title": compact_text(title, 300),
        "target": mission_action_target(payload.get("target") or payload.get("to")),
        "repo": str(payload.get("repo") or params.get("repo") or "").strip() or None,
        "sourceThread": mission_source_thread(payload.get("sourceThread") or payload.get("source_thread")),
        "priority": normalized_priority(payload.get("priority"), default=50),
        "params": params,
        "result": compact_text(payload.get("result"), 2000),
        "claimedBy": None,
        "linkedHandoffId": str(payload.get("linkedHandoffId") or payload.get("handoffId") or "").strip() or None,
        "linkedTaskId": str(payload.get("linkedTaskId") or payload.get("taskId") or "").strip() or None,
        "tags": [str(item).strip() for item in payload.get("tags", []) if str(item).strip()] if isinstance(payload.get("tags"), list) else [],
    }


def list_mission_items(kind, organization_id, limit=20, status=None, plan_id=None):
    state = load_handoff_inbox_state()
    key = "plansByOrg" if kind == "plan" else "tasksByOrg"
    rows = state.get(key, {}).get(organization_id, [])
    if not isinstance(rows, list):
        return []
    items = [row for row in rows if isinstance(row, dict)]
    if status:
        items = [item for item in items if item.get("status") == status]
    if plan_id:
        items = [item for item in items if item.get("planId") == plan_id]
    items.sort(key=lambda item: (normalized_priority(item.get("priority")), str(item.get("updatedAt") or "")))
    return items[: max(1, limit)]


def next_task_item(organization_id):
    candidates = []
    for status in ("in_progress", "assigned", "ready", "needs_review", "blocked", "backlog"):
        candidates.extend(list_mission_items("task", organization_id, limit=100, status=status))
    return candidates[0] if candidates else None


def list_mission_action_items(organization_id, limit=20, status=None, target_agent=None, target_host=None):
    state = load_handoff_inbox_state()
    rows = state.get("actionsByOrg", {}).get(organization_id, [])
    if not isinstance(rows, list):
        return []
    items = [row for row in rows if isinstance(row, dict)]
    if status:
        items = [item for item in items if item.get("status") == status]
    if target_agent:
        items = [item for item in items if ((item.get("target") or {}).get("agent") == target_agent)]
    if target_host:
        items = [item for item in items if ((item.get("target") or {}).get("host") in {None, "", target_host})]
    items.sort(key=lambda item: (normalized_priority(item.get("priority")), str(item.get("createdAt") or "")))
    return items[: max(1, limit)]


def get_mission_action_item(organization_id, action_id):
    state = load_handoff_inbox_state()
    rows = state.get("actionsByOrg", {}).get(organization_id, [])
    if not isinstance(rows, list):
        return None
    for item in rows:
        if isinstance(item, dict) and item.get("id") == action_id:
            return item
    return None


def next_mission_action_item(organization_id, target_agent=None, target_host=None):
    candidates = list_mission_action_items(
        organization_id,
        limit=100,
        status="queued",
        target_agent=target_agent,
        target_host=target_host,
    )
    return candidates[0] if candidates else None


def update_mission_item_status(kind, payload, item_id):
    organization_id = str(payload.get("organizationId") or "").strip()
    if not organization_id:
        raise ValueError("organizationId is required")
    next_status = normalized_mission_item_status(payload.get("status"), default="")
    if not next_status:
        raise ValueError("valid status is required")

    state = load_handoff_inbox_state()
    key = "plansByOrg" if kind == "plan" else "tasksByOrg"
    rows = state.setdefault(key, {}).setdefault(organization_id, [])
    if not isinstance(rows, list):
        rows = []
        state[key][organization_id] = rows

    for index, item in enumerate(rows):
        if not isinstance(item, dict) or str(item.get("id") or "") != item_id:
            continue
        updated = {**item, "status": next_status, "updatedAt": now()}
        if "result" in payload:
            updated["result"] = compact_text(payload.get("result"), 1200)
        if "assignee" in payload and kind == "task":
            updated["assignee"] = handoff_party(payload.get("assignee"), "macbook-codex", "codex-app")
        rows[index] = updated
        save_handoff_inbox_state(state)
        return organization_id, updated

    raise KeyError(f"{kind.title()} not found")


def update_mission_action_status(payload, action_id):
    organization_id = str(payload.get("organizationId") or "").strip()
    if not organization_id:
        raise ValueError("organizationId is required")
    next_status = normalized_mission_action_status(payload.get("status"), default="")
    if not next_status:
        raise ValueError("valid status is required")

    state = load_handoff_inbox_state()
    rows = state.setdefault("actionsByOrg", {}).setdefault(organization_id, [])
    if not isinstance(rows, list):
        rows = []
        state["actionsByOrg"][organization_id] = rows

    for index, item in enumerate(rows):
        if not isinstance(item, dict) or str(item.get("id") or "") != action_id:
            continue
        timestamp = now()
        updated = {**item, "status": next_status, "updatedAt": timestamp}
        if next_status in {"done", "failed", "blocked", "cancelled"}:
            updated["finishedAt"] = timestamp
        if "result" in payload:
            updated["result"] = compact_text(payload.get("result"), 2000)
        if "resultData" in payload:
            updated["resultData"] = payload.get("resultData")
        rows[index] = updated
        save_handoff_inbox_state(state)
        return organization_id, updated

    raise KeyError("Mission action not found")


def claim_mission_action(payload, action_id):
    organization_id = str(payload.get("organizationId") or "").strip()
    if not organization_id:
        raise ValueError("organizationId is required")
    worker_id = str(payload.get("workerId") or "").strip()
    if not worker_id:
        raise ValueError("workerId is required")

    state = load_handoff_inbox_state()
    rows = state.setdefault("actionsByOrg", {}).setdefault(organization_id, [])
    if not isinstance(rows, list):
        rows = []
        state["actionsByOrg"][organization_id] = rows

    for index, item in enumerate(rows):
        if not isinstance(item, dict) or str(item.get("id") or "") != action_id:
            continue
        if item.get("status") != "queued":
            return organization_id, None, item
        timestamp = now()
        updated = {
            **item,
            "status": "running",
            "updatedAt": timestamp,
            "startedAt": item.get("startedAt") or timestamp,
            "attempts": int(item.get("attempts") or 0) + 1,
            "claimedBy": worker_id,
        }
        rows[index] = updated
        save_handoff_inbox_state(state)
        return organization_id, updated, item

    raise KeyError("Mission action not found")


class Handler(BaseHTTPRequestHandler):
    def _json(self, code, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _require_auth(self, scope="read"):
        if not REQUIRE_TOKEN:
            return {"scope": scope, "role": "admin"}

        auth = self.headers.get("Authorization", "")
        token = auth.replace("Bearer ", "", 1) if auth.startswith("Bearer ") else ""
        header_key = self.headers.get("x-hermes-api-key", "").strip()

        if scope == "read":
            read_candidates = [value for value in {READ_TOKEN, EXEC_ADMIN_TOKEN, EXEC_OPERATOR_TOKEN} if value]
            if not read_candidates:
                self._json(500, {"ok": False, "error": "server_read_token_not_configured"})
                return None
            if token not in read_candidates and header_key not in read_candidates:
                self._json(401, {"ok": False, "error": "unauthorized", "scope": scope})
                return None
            return {"scope": "read", "role": "viewer"}

        admin = EXEC_ADMIN_TOKEN
        operator = EXEC_OPERATOR_TOKEN
        if not admin and not operator:
            self._json(500, {"ok": False, "error": "server_exec_token_not_configured"})
            return None

        if admin and (token == admin or header_key == admin):
            return {"scope": "exec", "role": "admin"}
        if operator and (token == operator or header_key == operator):
            return {"scope": "exec", "role": "operator"}

        self._json(401, {"ok": False, "error": "unauthorized", "scope": scope})
        return None

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)

        if parsed.path == "/health":
            return self._json(200, {
                "ok": True,
                "time": now(),
                "auth_required": REQUIRE_TOKEN,
                "auth_mode": "split" if (READ_TOKEN != EXEC_TOKEN) else "single",
                "exec_roles": {
                    "admin_enabled": bool(EXEC_ADMIN_TOKEN),
                    "operator_enabled": bool(EXEC_OPERATOR_TOKEN),
                    "operator_actions": sorted(ROLE_ACTIONS.get("operator", set())),
                },
                "mode_recommendation": summarize_mode_recommendation(),
                "audit_log": str(AUDIT_LOG),
                "knowledge_dir": str(KNOWLEDGE_DIR),
                "knowledge_autogit": KNOWLEDGE_AUTOGIT,
                "lock_file": str(LOCK_PATH),
                "continuity_notify_enabled": True,
                "continuity_notify_log": str(HANDOFF_NOTIFY_LOG),
                "handoff_inbox": str(HANDOFF_INBOX_PATH),
                "handoff_inbox_legacy": str(LEGACY_HANDOFF_INBOX_PATH),
                "mission_control": {
                    "plans_enabled": True,
                    "tasks_enabled": True,
                    "next_task_enabled": True,
                    "actions_enabled": True,
                    "next_action_enabled": True,
                    "snapshot_enabled": True,
                },
            })

        if parsed.path == "/snapshot":
            auth_ctx = self._require_auth("read")
            if REQUIRE_TOKEN and not auth_ctx:
                return
            organization_id = (params.get("organizationId") or [""])[0].strip()
            if not organization_id:
                return self._json(400, {"ok": False, "error": "organizationId_required"})
            return self._json(200, {
                "ok": True,
                "success": True,
                "data": {
                    "plans": list_mission_items("plan", organization_id, limit=30),
                    "tasks": list_mission_items("task", organization_id, limit=50),
                    "nextTask": next_task_item(organization_id),
                    "actions": list_mission_action_items(organization_id, limit=50),
                    "nextAction": next_mission_action_item(organization_id),
                    "handoffs": list_handoff_items(organization_id, limit=30),
                },
            })

        if parsed.path == "/plans":
            auth_ctx = self._require_auth("read")
            if REQUIRE_TOKEN and not auth_ctx:
                return
            organization_id = (params.get("organizationId") or [""])[0].strip()
            if not organization_id:
                return self._json(400, {"ok": False, "error": "organizationId_required"})
            try:
                limit = max(1, min(100, int((params.get("limit") or ["20"])[0])))
            except Exception:
                limit = 20
            status = (params.get("status") or [""])[0].strip() or None
            items = list_mission_items("plan", organization_id, limit=limit, status=status)
            return self._json(200, {"ok": True, "success": True, "items": items, "data": items})

        if parsed.path == "/tasks/next":
            auth_ctx = self._require_auth("read")
            if REQUIRE_TOKEN and not auth_ctx:
                return
            organization_id = (params.get("organizationId") or [""])[0].strip()
            if not organization_id:
                return self._json(400, {"ok": False, "error": "organizationId_required"})
            item = next_task_item(organization_id)
            return self._json(200, {"ok": True, "success": True, "item": item, "data": item})

        if parsed.path == "/tasks":
            auth_ctx = self._require_auth("read")
            if REQUIRE_TOKEN and not auth_ctx:
                return
            organization_id = (params.get("organizationId") or [""])[0].strip()
            if not organization_id:
                return self._json(400, {"ok": False, "error": "organizationId_required"})
            try:
                limit = max(1, min(100, int((params.get("limit") or ["20"])[0])))
            except Exception:
                limit = 20
            status = (params.get("status") or [""])[0].strip() or None
            plan_id = (params.get("planId") or [""])[0].strip() or None
            items = list_mission_items("task", organization_id, limit=limit, status=status, plan_id=plan_id)
            return self._json(200, {"ok": True, "success": True, "items": items, "data": items})

        if parsed.path == "/mission-actions/next":
            auth_ctx = self._require_auth("read")
            if REQUIRE_TOKEN and not auth_ctx:
                return
            organization_id = (params.get("organizationId") or [""])[0].strip()
            if not organization_id:
                return self._json(400, {"ok": False, "error": "organizationId_required"})
            target_agent = (params.get("targetAgent") or [""])[0].strip() or None
            target_host = (params.get("targetHost") or [""])[0].strip() or None
            item = next_mission_action_item(organization_id, target_agent=target_agent, target_host=target_host)
            return self._json(200, {"ok": True, "success": True, "item": item, "data": item})

        if parsed.path.startswith("/mission-actions/") and len(parsed.path.split("/")) == 3:
            auth_ctx = self._require_auth("read")
            if REQUIRE_TOKEN and not auth_ctx:
                return
            action_id = parsed.path.split("/")[2]
            organization_id = (params.get("organizationId") or [""])[0].strip()
            if not organization_id:
                return self._json(400, {"ok": False, "error": "organizationId_required"})
            item = get_mission_action_item(organization_id, action_id)
            if item is None:
                return self._json(404, {"ok": False, "error": "mission_action_not_found"})
            return self._json(200, {"ok": True, "success": True, "item": item, "data": item})

        if parsed.path == "/mission-actions":
            auth_ctx = self._require_auth("read")
            if REQUIRE_TOKEN and not auth_ctx:
                return
            organization_id = (params.get("organizationId") or [""])[0].strip()
            if not organization_id:
                return self._json(400, {"ok": False, "error": "organizationId_required"})
            try:
                limit = max(1, min(100, int((params.get("limit") or ["20"])[0])))
            except Exception:
                limit = 20
            status = (params.get("status") or [""])[0].strip() or None
            target_agent = (params.get("targetAgent") or [""])[0].strip() or None
            target_host = (params.get("targetHost") or [""])[0].strip() or None
            items = list_mission_action_items(
                organization_id,
                limit=limit,
                status=status,
                target_agent=target_agent,
                target_host=target_host,
            )
            return self._json(200, {"ok": True, "success": True, "items": items, "data": items})

        if parsed.path == "/handoffs":
            auth_ctx = self._require_auth("read")
            if REQUIRE_TOKEN and not auth_ctx:
                return
            organization_id = (params.get("organizationId") or [""])[0].strip()
            if not organization_id:
                return self._json(400, {"ok": False, "error": "organizationId_required"})
            try:
                limit = max(1, min(100, int((params.get("limit") or ["20"])[0])))
            except Exception:
                limit = 20
            status = (params.get("status") or [""])[0].strip() or None
            items = list_handoff_items(organization_id, limit=limit, status=status)
            return self._json(200, {"ok": True, "success": True, "items": items, "data": items})

        if parsed.path.startswith("/actions/recent"):
            auth_ctx = self._require_auth("read")
            if REQUIRE_TOKEN and not auth_ctx:
                return
            return self._json(200, {"ok": True, "items": read_recent_audits(20)})

        if self.path.startswith("/knowledge/recent"):
            auth_ctx = self._require_auth("read")
            if REQUIRE_TOKEN and not auth_ctx:
                return
            return self._json(200, {"ok": True, "items": read_recent_knowledge(20)})

        if self.path.startswith("/knowledge/graph"):
            auth_ctx = self._require_auth("read")
            if REQUIRE_TOKEN and not auth_ctx:
                return
            return self._json(200, build_knowledge_graph(50))

        if self.path.startswith("/fsm/state"):
            auth_ctx = self._require_auth("read")
            if REQUIRE_TOKEN and not auth_ctx:
                return
            return self._json(200, build_fsm_snapshot(20))

        return self._json(404, {"ok": False, "error": "not_found"})

    def do_POST(self):
        auth_ctx = None
        parsed = urlparse(self.path)
        if parsed.path in {"/action", "/knowledge/inject", "/handoffs", "/plans", "/tasks", "/mission-actions"} or (
            parsed.path.startswith("/handoffs/") and parsed.path.endswith("/status")
        ) or (
            parsed.path.startswith("/plans/") and parsed.path.endswith("/status")
        ) or (
            parsed.path.startswith("/tasks/") and parsed.path.endswith("/status")
        ) or (
            parsed.path.startswith("/mission-actions/") and parsed.path.endswith("/status")
        ) or (
            parsed.path.startswith("/mission-actions/") and parsed.path.endswith("/claim")
        ):
            auth_ctx = self._require_auth("exec")
            if REQUIRE_TOKEN and not auth_ctx:
                return
        elif parsed.path == "/handoff/notify":
            auth_ctx = self._require_auth("read")
            if REQUIRE_TOKEN and not auth_ctx:
                return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length) if length > 0 else b"{}"
            data = json.loads(raw.decode("utf-8"))
        except Exception:
            return self._json(400, {"ok": False, "error": "invalid_json"})

        if parsed.path == "/handoff/notify":
            event = dict(data) if isinstance(data, dict) else {"payload": data}
            event["receivedAt"] = now()
            append_jsonl(HANDOFF_NOTIFY_LOG, event)
            audit({
                "time": now(),
                "action": "continuity_handoff_notify",
                "ok": True,
                "handoffId": event.get("handoffId"),
                "runId": event.get("runId")
                or ((event.get("source") or {}).get("runId") if isinstance(event.get("source"), dict) else None),
            })
            return self._json(200, {
                "ok": True,
                "receivedAt": event["receivedAt"],
                "storedAt": str(HANDOFF_NOTIFY_LOG),
                "validationErrors": [],
            })

        if parsed.path == "/plans":
            try:
                organization_id, item = create_plan_item(data)
            except ValueError as error:
                return self._json(400, {"ok": False, "error": str(error)})
            with RUNTIME_LOCK:
                state = load_handoff_inbox_state()
                rows = state.setdefault("plansByOrg", {}).setdefault(organization_id, [])
                if not isinstance(rows, list):
                    rows = []
                    state["plansByOrg"][organization_id] = rows
                rows.append(item)
                rows.sort(key=lambda row: (normalized_priority(row.get("priority")), str(row.get("updatedAt") or "")))
                save_handoff_inbox_state(state)
            audit({
                "time": now(),
                "action": "plan_created",
                "ok": True,
                "organizationId": organization_id,
                "planId": item["id"],
                "status": item["status"],
            })
            return self._json(200, {"ok": True, "success": True, "item": item, "data": item})

        if parsed.path.startswith("/plans/") and parsed.path.endswith("/status"):
            plan_id = parsed.path.split("/")[2]
            try:
                organization_id, item = update_mission_item_status("plan", data, plan_id)
            except ValueError as error:
                return self._json(400, {"ok": False, "error": str(error)})
            except KeyError:
                return self._json(404, {"ok": False, "error": "plan_not_found"})
            audit({
                "time": now(),
                "action": "plan_status_updated",
                "ok": True,
                "organizationId": organization_id,
                "planId": item["id"],
                "status": item["status"],
            })
            return self._json(200, {"ok": True, "success": True, "item": item, "data": item})

        if parsed.path == "/tasks":
            try:
                organization_id, item = create_task_item(data)
            except ValueError as error:
                return self._json(400, {"ok": False, "error": str(error)})
            with RUNTIME_LOCK:
                state = load_handoff_inbox_state()
                rows = state.setdefault("tasksByOrg", {}).setdefault(organization_id, [])
                if not isinstance(rows, list):
                    rows = []
                    state["tasksByOrg"][organization_id] = rows
                rows.append(item)
                rows.sort(key=lambda row: (normalized_priority(row.get("priority")), str(row.get("updatedAt") or "")))
                save_handoff_inbox_state(state)
            audit({
                "time": now(),
                "action": "task_created",
                "ok": True,
                "organizationId": organization_id,
                "taskId": item["id"],
                "status": item["status"],
                "planId": item.get("planId"),
            })
            return self._json(200, {"ok": True, "success": True, "item": item, "data": item})

        if parsed.path.startswith("/tasks/") and parsed.path.endswith("/status"):
            task_id = parsed.path.split("/")[2]
            try:
                organization_id, item = update_mission_item_status("task", data, task_id)
            except ValueError as error:
                return self._json(400, {"ok": False, "error": str(error)})
            except KeyError:
                return self._json(404, {"ok": False, "error": "task_not_found"})
            audit({
                "time": now(),
                "action": "task_status_updated",
                "ok": True,
                "organizationId": organization_id,
                "taskId": item["id"],
                "status": item["status"],
            })
            return self._json(200, {"ok": True, "success": True, "item": item, "data": item})

        if parsed.path == "/mission-actions":
            try:
                organization_id, item = create_mission_action_item(data)
            except ValueError as error:
                return self._json(400, {"ok": False, "error": str(error)})
            with RUNTIME_LOCK:
                state = load_handoff_inbox_state()
                rows = state.setdefault("actionsByOrg", {}).setdefault(organization_id, [])
                if not isinstance(rows, list):
                    rows = []
                    state["actionsByOrg"][organization_id] = rows
                rows.append(item)
                rows.sort(key=lambda row: (normalized_priority(row.get("priority")), str(row.get("createdAt") or "")))
                save_handoff_inbox_state(state)
            audit({
                "time": now(),
                "action": "mission_action_created",
                "ok": True,
                "organizationId": organization_id,
                "missionActionId": item["id"],
                "actionType": item["actionType"],
                "status": item["status"],
            })
            return self._json(200, {"ok": True, "success": True, "item": item, "data": item})

        if parsed.path.startswith("/mission-actions/") and parsed.path.endswith("/claim"):
            action_id = parsed.path.split("/")[2]
            try:
                organization_id, item, previous = claim_mission_action(data, action_id)
            except ValueError as error:
                return self._json(400, {"ok": False, "error": str(error)})
            except KeyError:
                return self._json(404, {"ok": False, "error": "mission_action_not_found"})
            if item is None:
                return self._json(409, {
                    "ok": False,
                    "error": "mission_action_not_queued",
                    "item": previous,
                    "data": previous,
                })
            audit({
                "time": now(),
                "action": "mission_action_claimed",
                "ok": True,
                "organizationId": organization_id,
                "missionActionId": item["id"],
                "workerId": item.get("claimedBy"),
            })
            return self._json(200, {"ok": True, "success": True, "item": item, "data": item})

        if parsed.path.startswith("/mission-actions/") and parsed.path.endswith("/status"):
            action_id = parsed.path.split("/")[2]
            try:
                organization_id, item = update_mission_action_status(data, action_id)
            except ValueError as error:
                return self._json(400, {"ok": False, "error": str(error)})
            except KeyError:
                return self._json(404, {"ok": False, "error": "mission_action_not_found"})
            audit({
                "time": now(),
                "action": "mission_action_status_updated",
                "ok": True,
                "organizationId": organization_id,
                "missionActionId": item["id"],
                "status": item["status"],
            })
            return self._json(200, {"ok": True, "success": True, "item": item, "data": item})

        if parsed.path == "/handoffs":
            try:
                organization_id, item = create_handoff_item(data)
            except ValueError as error:
                return self._json(400, {"ok": False, "error": str(error)})
            with RUNTIME_LOCK:
                state = load_handoff_inbox_state()
                rows = state.setdefault("handoffsByOrg", {}).setdefault(organization_id, [])
                if not isinstance(rows, list):
                    rows = []
                    state["handoffsByOrg"][organization_id] = rows
                rows.append(item)
                rows.sort(key=lambda row: str(row.get("updatedAt") or row.get("createdAt") or ""), reverse=True)
                save_handoff_inbox_state(state)
            audit({
                "time": now(),
                "action": "handoff_created",
                "ok": True,
                "organizationId": organization_id,
                "handoffId": item["id"],
                "status": item["status"],
                "repo": item.get("repo"),
            })
            return self._json(200, {"ok": True, "success": True, "item": item, "data": item})

        if parsed.path.startswith("/handoffs/") and parsed.path.endswith("/status"):
            handoff_id = parsed.path.split("/")[2]
            try:
                organization_id, item = update_handoff_status(data, handoff_id)
            except ValueError as error:
                return self._json(400, {"ok": False, "error": str(error)})
            except KeyError:
                return self._json(404, {"ok": False, "error": "handoff_not_found"})
            audit({
                "time": now(),
                "action": "handoff_status_updated",
                "ok": True,
                "organizationId": organization_id,
                "handoffId": item["id"],
                "status": item["status"],
            })
            return self._json(200, {"ok": True, "success": True, "item": item, "data": item})

        if parsed.path == "/knowledge/inject":
            role = (auth_ctx or {}).get("role", "admin")
            title = str(data.get("title", "")).strip() or "untitled"
            content = str(data.get("content", "")).strip()
            tags = data.get("tags") if isinstance(data.get("tags"), list) else []
            source = str(data.get("source", "manual")).strip()
            if not content:
                return self._json(400, {"ok": False, "error": "content_required"})

            raw_path = knowledge_note_path("inject", title)
            wiki_path = knowledge_wiki_path("inject", title)
            raw_md = "\n".join([
                f"# {title}",
                f"- time: {now()}",
                f"- source: {source}",
                f"- role: {role}",
                f"- tags: {', '.join(map(str, tags)) if tags else '-'}",
                "",
                "## content",
                content,
                "",
            ])
            save_markdown(raw_path, raw_md)

            wiki_md = "\n".join([
                f"# Decision Note: {title}",
                f"- date: {today()}",
                f"- source: {source}",
                f"- tags: {', '.join(map(str, tags)) if tags else '-'}",
                f"- linked_raw: {raw_path.relative_to(ROOT)}",
                "",
                "## summary",
                content[:1000],
                "",
            ])
            save_markdown(wiki_path, wiki_md)
            autogit = safe_autogit([str(raw_path.relative_to(ROOT)), str(wiki_path.relative_to(ROOT))], f"ops-knowledge: inject {slug(title)}")
            audit({"time": now(), "action": "knowledge_inject", "role": role, "ok": True, "title": title})
            return self._json(200, {
                "ok": True,
                "raw_path": str(raw_path.relative_to(ROOT)),
                "wiki_path": str(wiki_path.relative_to(ROOT)),
                "autogit": autogit,
            })

        if parsed.path != "/action":
            return self._json(404, {"ok": False, "error": "not_found"})

        action = str(data.get("action", "")).strip()
        dry_run = bool(data.get("dry_run", False))
        raw_profiles = data.get("profile_ids", [])
        if isinstance(raw_profiles, str):
            raw_profiles = [raw_profiles]
        profile_ids = [str(p).strip() for p in raw_profiles if str(p).strip()][:20]
        seq = COMMANDS.get(action)
        if not seq:
            return self._json(400, {"ok": False, "error": "unknown_action", "allowed": sorted(COMMANDS)})

        role = (auth_ctx or {}).get("role", "admin")
        allowed_actions = ROLE_ACTIONS.get(role, set())
        if action not in allowed_actions:
            return self._json(403, {
                "ok": False,
                "error": "forbidden_action",
                "role": role,
                "allowed_actions": sorted(allowed_actions),
            })

        if dry_run:
            payload = {
                "ok": True,
                "dry_run": True,
                "action": action,
                "role": role,
                "profile_ids": profile_ids,
                "commands": [" ".join(c) for c in seq],
            }
            audit({"time": now(), "action": action, "role": role, "profile_ids": profile_ids, "dry_run": True, "ok": True})
            return self._json(200, payload)

        with RUNTIME_LOCK:
            if LOCK_PATH.exists():
                return self._json(409, {"ok": False, "error": "busy", "lock_file": str(LOCK_PATH)})
            _ensure_parent(LOCK_PATH)
            LOCK_PATH.write_text(now(), encoding="utf-8")

            try:
                results = [run_cmd(c) for c in seq]
                ok = all(r["exit_code"] == 0 for r in results)
                payload = {
                    "ok": ok,
                    "action": action,
                    "role": role,
                    "profile_ids": profile_ids,
                    "time": now(),
                    "results": results,
                }
                knowledge = None
                autogit = {"enabled": False}
                if ok:
                    knowledge = harvest_lineage_knowledge(action, role)
                    autogit = safe_autogit(
                        [knowledge["raw_path"], knowledge["wiki_path"]],
                        f"ops-knowledge: {action} mode {knowledge['mode'].lower()}"
                    )
                    payload["knowledge"] = knowledge
                    payload["autogit"] = autogit
                audit({
                    "time": payload["time"],
                    "action": action,
                    "role": role,
                    "profile_ids": profile_ids,
                    "ok": ok,
                    "result_count": len(results),
                    "knowledge": knowledge,
                    "failed_commands": [r["cmd"] for r in results if r["exit_code"] != 0],
                })
                return self._json(200 if ok else 500, payload)
            finally:
                try:
                    LOCK_PATH.unlink(missing_ok=True)
                except Exception:
                    pass

    def log_message(self, format, *args):
        return


if __name__ == "__main__":
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"ops-control-api listening on http://{HOST}:{PORT} (auth_required={REQUIRE_TOKEN}, auth_mode={'split' if READ_TOKEN != EXEC_TOKEN else 'single'})")
    server.serve_forever()
