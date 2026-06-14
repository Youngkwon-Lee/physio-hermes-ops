#!/usr/bin/env python3
from __future__ import annotations
import base64
import json
import os
import subprocess
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Lock
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, quote, urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[2]
HOST = os.getenv("HERMES_MISSION_CONTROL_HOST", "127.0.0.1")
PORT = int(os.getenv("HERMES_MISSION_CONTROL_PORT", "8791"))
API_KEY = os.getenv("HERMES_MISSION_CONTROL_API_KEY", "").strip()
STATE_PATH = Path(
    os.getenv(
        "HERMES_MISSION_CONTROL_STATE_PATH",
        str(ROOT / ".runtime" / "mission_control" / "state.json"),
    )
)
EVENT_LOG = Path(
    os.getenv(
        "HERMES_MISSION_CONTROL_EVENT_LOG",
        str(ROOT / "lineage" / "mission_control_events.jsonl"),
    )
)
HANDOFF_NOTIFY_LOG = Path(
    os.getenv(
        "HERMES_MISSION_CONTROL_HANDOFF_NOTIFY_LOG",
        str(ROOT / "lineage" / "continuity_handoff_notifications.jsonl"),
    )
)
A2A_STATE_DIR = Path(
    os.getenv(
        "HERMES_MISSION_CONTROL_A2A_STATE_DIR",
        str(ROOT / ".runtime" / "continuity_a2a_lite"),
    )
)
A2A_MESSAGE_LOG = Path(
    os.getenv(
        "HERMES_MISSION_CONTROL_A2A_MESSAGE_LOG",
        str(ROOT / "lineage" / "continuity_a2a_lite_messages.jsonl"),
    )
)
A2A_AUTO_ACTION_LOG = Path(
    os.getenv(
        "HERMES_MISSION_CONTROL_A2A_AUTO_ACTION_LOG",
        str(ROOT / "lineage" / "continuity_handoff_auto_actions.jsonl"),
    )
)
HANDOFF_INBOX_PATH = Path(
    os.getenv(
        "HERMES_MISSION_CONTROL_HANDOFF_INBOX_PATH",
        str(ROOT / ".runtime" / "mission_control" / "handoff_inbox.json"),
    )
)
DEFAULT_STALE_MINUTES = max(1, int(os.getenv("HERMES_MISSION_CONTROL_STALE_MINUTES", "30")))
DEFAULT_A2A_LIMIT = max(1, int(os.getenv("HERMES_MISSION_CONTROL_A2A_LIMIT", "20")))
DEFAULT_HANDOFF_LIMIT = max(1, int(os.getenv("HERMES_MISSION_CONTROL_HANDOFF_LIMIT", "20")))
STATE_LOCK = Lock()


LANES: dict[str, dict[str, Any]] = {
    "feature": {
        "name": "Feature Lane",
        "label": "기능개발",
        "objective": "새 제품 기능을 PRD, issue, PR, preview, deploy approval로 이동시킨다.",
        "defaultWorkflowIds": ["prd-to-issue", "issue-to-pr", "pr-to-deploy"],
        "primaryAgents": ["planner", "orchestrator", "frontend", "backend", "db", "qa", "devops"],
        "approvalGates": ["plan", "issue", "pull-request", "preview", "production"],
        "defaultGreenLevel": "release-ready",
    },
    "maintenance": {
        "name": "Maintenance Lane",
        "label": "유지보수",
        "objective": "버그, 회귀, flaky test, 성능 저하, 기술부채를 작은 fix PR로 정리한다.",
        "defaultWorkflowIds": ["issue-to-pr"],
        "primaryAgents": ["orchestrator", "qa", "frontend", "backend"],
        "approvalGates": ["pull-request"],
        "defaultGreenLevel": "merge-ready",
    },
    "devops": {
        "name": "DevOps Lane",
        "label": "배포/운영",
        "objective": "CI/CD, preview, production deploy, incident response, rollback을 승인 중심으로 운영한다.",
        "defaultWorkflowIds": ["pr-to-deploy"],
        "primaryAgents": ["devops", "qa", "orchestrator"],
        "approvalGates": ["preview", "production"],
        "defaultGreenLevel": "release-ready",
    },
    "mlops": {
        "name": "MLOps Lane",
        "label": "모델/평가",
        "objective": "LLM 품질, prompt, eval set, 비용, 실패 케이스를 개선 PR로 연결한다.",
        "defaultWorkflowIds": ["self-improvement"],
        "primaryAgents": ["qa", "backend", "orchestrator"],
        "approvalGates": ["plan", "pull-request"],
        "defaultGreenLevel": "merge-ready",
    },
    "growth": {
        "name": "Growth Lane",
        "label": "퍼널/성장",
        "objective": "랜딩, 가입, 온보딩, 리텐션, 가격/패키지 실험을 issue와 PR로 만든다.",
        "defaultWorkflowIds": ["daily-ops", "prd-to-issue", "issue-to-pr"],
        "primaryAgents": ["planner", "frontend", "qa", "orchestrator"],
        "approvalGates": ["plan", "issue", "pull-request", "preview"],
        "defaultGreenLevel": "workspace",
    },
    "db-data": {
        "name": "DB/Data Lane",
        "label": "DB/데이터",
        "objective": "schema, RLS, 데이터 품질, ontology drift, DB 문서 동기화를 관리한다.",
        "defaultWorkflowIds": ["issue-to-pr"],
        "primaryAgents": ["db", "backend", "qa", "orchestrator"],
        "approvalGates": ["migration", "pull-request", "production"],
        "defaultGreenLevel": "release-ready",
    },
    "ops-finance": {
        "name": "Ops/Finance Lane",
        "label": "운영/비용",
        "objective": "usage, AI 비용, 운영 리스크, 주간 브리프, 고객지원 후속 조치를 정리한다.",
        "defaultWorkflowIds": ["daily-ops", "prd-to-issue", "self-improvement"],
        "primaryAgents": ["orchestrator", "planner", "devops", "qa"],
        "approvalGates": ["plan", "issue"],
        "defaultGreenLevel": "targeted",
    },
}

APPROVAL_LABELS = {
    "plan": "Approve plan",
    "issue": "Create issues",
    "pull-request": "Approve PR",
    "migration": "Approve migration",
    "preview": "Approve preview",
    "production": "Approve deploy",
}

DEFAULT_APPROVAL_AGENTS = {
    "migration": "db",
    "preview": "devops",
    "production": "devops",
    "pull-request": "qa",
    "plan": "orchestrator",
    "issue": "orchestrator",
}

def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return deepcopy(default)


def write_json(path: Path, payload: Any) -> None:
    ensure_parent(path)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            parsed = json.loads(line)
        except Exception:
            continue
        if isinstance(parsed, dict):
            rows.append(parsed)
    return rows


def append_jsonl(path: Path, row: dict[str, Any]) -> None:
    ensure_parent(path)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def ok(data: Any) -> dict[str, Any]:
    return {"success": True, "data": data}


def err(message: str, code: str = "INTERNAL_ERROR") -> dict[str, Any]:
    return {"success": False, "error": message, "code": code}


def compact_text(value: Any, limit: int = 180) -> str | None:
    text = str(value or "").strip().replace("\n", " ")
    if not text:
        return None
    return text if len(text) <= limit else text[: limit - 1] + "…"


def is_enabled(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def env_value(key: str) -> str | None:
    value = os.getenv(key)
    if value is None:
        return None
    trimmed = value.strip()
    return trimmed or None


def env_group_missing(group: str) -> list[str]:
    keys = [part.strip() for part in group.split("|") if part.strip()]
    if any(env_value(key) for key in keys):
        return []
    return keys


def base_state() -> dict[str, Any]:
    return {
        "version": 1,
        "updatedAt": now_iso(),
        "runsByOrg": {},
    }


def load_state() -> dict[str, Any]:
    state = read_json(STATE_PATH, base_state())
    if not isinstance(state, dict):
        return base_state()
    if "runsByOrg" not in state or not isinstance(state["runsByOrg"], dict):
        state["runsByOrg"] = {}
    return state


def save_state(state: dict[str, Any]) -> None:
    state["updatedAt"] = now_iso()
    write_json(STATE_PATH, state)


def log_event(kind: str, payload: dict[str, Any]) -> None:
    append_jsonl(
        EVENT_LOG,
        {
            "timestamp": now_iso(),
            "kind": kind,
            **payload,
        },
    )


def minutes_since(value: str) -> int:
    created = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return max(0, int((datetime.now(timezone.utc) - created).total_seconds() // 60))


def sort_runs_desc(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(items, key=lambda item: item.get("updatedAt", ""), reverse=True)


def get_runs_for_org(state: dict[str, Any], organization_id: str) -> list[dict[str, Any]]:
    items = state.get("runsByOrg", {}).get(organization_id, [])
    if not isinstance(items, list):
        return []
    return sort_runs_desc(items)


def set_runs_for_org(state: dict[str, Any], organization_id: str, runs: list[dict[str, Any]]) -> None:
    state.setdefault("runsByOrg", {})[organization_id] = sort_runs_desc(runs)


def find_run(state: dict[str, Any], organization_id: str, run_id: str) -> tuple[int, dict[str, Any] | None]:
    runs = state.get("runsByOrg", {}).get(organization_id, [])
    for index, run in enumerate(runs):
        if run.get("id") == run_id:
            return index, run
    return -1, None


def approval_label(gate: str) -> str:
    return APPROVAL_LABELS.get(gate, gate)


def default_approval_agent(gate: str) -> str:
    return DEFAULT_APPROVAL_AGENTS.get(gate, "orchestrator")


def delivery_status(payload: Any) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    status_code = payload.get("status_code")
    return {
        "attempted": bool(payload.get("attempted")),
        "ok": bool(payload.get("ok")),
        "statusCode": int(status_code) if isinstance(status_code, int) else None,
        "url": str(payload.get("url") or "").strip() or None,
        "error": compact_text(payload.get("error"), 200),
    }


def summarize_a2a_conversation(
    state: str,
    callback: dict[str, Any] | None,
    question: dict[str, Any] | None,
    result: dict[str, Any] | None,
) -> str:
    callback_ok = bool(callback and callback.get("ok"))
    if state == "waiting_for_answer":
        if question and callback_ok:
            return "Desktop sent a clarification question and is waiting for a reply."
        if question:
            return "Desktop generated a clarification question, but callback delivery did not confirm success."
        return "Conversation is waiting for an answer."
    if state == "done":
        if result and callback_ok:
            return "Conversation completed and the final result callback was delivered."
        if result:
            return "Conversation completed and produced a final result."
        return "Conversation completed."
    if state == "blocked":
        return "Conversation is blocked and needs operator attention."
    if state == "cancelled":
        return "Conversation was cancelled."
    if state == "request_received":
        return "Conversation was received and is waiting for desktop processing."
    return compact_text(f"Conversation state is {state}.", 120) or "Conversation state is unknown."


def link_a2a_runs(runs: list[dict[str, Any]], thread_id: str | None) -> list[str]:
    if not thread_id:
        return []
    linked: list[str] = []
    for run in runs:
        source = run.get("source") if isinstance(run.get("source"), dict) else {}
        if str(source.get("threadId") or "").strip() == thread_id:
            linked.append(str(run.get("id")))
    return linked


def list_a2a_lite_conversations(
    *,
    limit: int = DEFAULT_A2A_LIMIT,
    runs: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    state_rows: dict[str, dict[str, Any]] = {}
    if A2A_STATE_DIR.exists():
        for path in sorted(A2A_STATE_DIR.glob("*.json")):
            row = read_json(path, {})
            if not isinstance(row, dict):
                continue
            conversation_id = str(row.get("conversationId") or "").strip()
            if conversation_id:
                state_rows[conversation_id] = row

    payload_rows: dict[str, list[dict[str, Any]]] = {}
    for row in read_jsonl(HANDOFF_NOTIFY_LOG):
        if str(row.get("schema") or "").strip() != "continuity_a2a_lite_v0_1":
            continue
        conversation_id = str(row.get("conversationId") or "").strip()
        if not conversation_id:
            continue
        payload_rows.setdefault(conversation_id, []).append(row)

    message_rows: dict[str, list[dict[str, Any]]] = {}
    for row in read_jsonl(A2A_MESSAGE_LOG):
        conversation_id = str(row.get("conversationId") or "").strip()
        if not conversation_id:
            continue
        message_rows.setdefault(conversation_id, []).append(row)

    action_rows: dict[str, list[dict[str, Any]]] = {}
    for row in read_jsonl(A2A_AUTO_ACTION_LOG):
        conversation_id = str(row.get("conversation_id") or "").strip()
        if not conversation_id:
            continue
        action_rows.setdefault(conversation_id, []).append(row)

    all_ids = set(state_rows) | set(payload_rows) | set(message_rows) | set(action_rows)
    items: list[dict[str, Any]] = []
    known_runs = runs or []
    for conversation_id in all_ids:
        state_row = state_rows.get(conversation_id, {})
        payloads = payload_rows.get(conversation_id, [])
        messages = message_rows.get(conversation_id, [])
        actions = action_rows.get(conversation_id, [])

        request_payload = next((row for row in payloads if str(row.get("role") or "").strip() == "request"), payloads[0] if payloads else {})
        latest_payload = payloads[-1] if payloads else {}
        latest_action = actions[-1] if actions else {}
        last_question = next((row for row in reversed(actions) if str(row.get("reply_role") or "").strip() == "question"), None)
        last_result = next((row for row in reversed(actions) if str(row.get("reply_role") or "").strip() == "result"), None)
        latest_request_payload = next((row for row in reversed(payloads) if str(row.get("role") or "").strip() == "request"), None)
        latest_answer_payload = next((row for row in reversed(payloads) if str(row.get("role") or "").strip() == "answer"), None)
        latest_callback = delivery_status(state_row.get("lastCallbackDelivery")) or delivery_status(latest_action.get("callback_delivery"))

        context = latest_payload.get("context") if isinstance(latest_payload.get("context"), dict) else {}
        if not context and isinstance(request_payload.get("context"), dict):
            context = request_payload.get("context")
        source_from = latest_payload.get("from") if isinstance(latest_payload.get("from"), dict) else {}
        if not source_from and isinstance(request_payload.get("from"), dict):
            source_from = request_payload.get("from")
        target_to = latest_payload.get("to") if isinstance(latest_payload.get("to"), dict) else {}
        if not target_to and isinstance(request_payload.get("to"), dict):
            target_to = request_payload.get("to")

        state_name = str(state_row.get("state") or latest_action.get("conversation_state") or "unknown").strip()
        updated_at = (
            str(state_row.get("updatedAt") or "").strip()
            or str(latest_action.get("timestamp") or "").strip()
            or str(latest_payload.get("receivedAt") or "").strip()
            or str(request_payload.get("receivedAt") or "").strip()
        )
        inbound_count = sum(1 for row in messages if str(row.get("direction") or "").startswith("inbound"))
        outbound_count = sum(1 for row in messages if str(row.get("direction") or "") == "outbound")
        thread_id = str(context.get("threadId") or "").strip() or None

        items.append(
            {
                "conversationId": conversation_id,
                "state": state_name,
                "updatedAt": updated_at,
                "latestRole": str(state_row.get("latestRole") or latest_payload.get("role") or "").strip() or None,
                "latestMessageId": str(state_row.get("latestMessageId") or latest_payload.get("messageId") or "").strip() or None,
                "latestReplyTo": str(state_row.get("latestReplyTo") or latest_payload.get("replyTo") or "").strip() or None,
                "goal": compact_text(latest_payload.get("goal") or request_payload.get("goal"), 200),
                "summary": summarize_a2a_conversation(state_name, latest_callback, last_question, last_result),
                "from": {
                    "agent": str(source_from.get("agent") or "").strip() or None,
                    "surface": str(source_from.get("surface") or "").strip() or None,
                    "host": str(source_from.get("host") or "").strip() or None,
                },
                "to": {
                    "agent": str(target_to.get("agent") or "").strip() or None,
                    "surface": str(target_to.get("surface") or "").strip() or None,
                    "host": str(target_to.get("host") or "").strip() or None,
                },
                "context": {
                    "repo": str(context.get("repo") or "").strip() or None,
                    "branch": str(context.get("branch") or "").strip() or None,
                    "threadId": thread_id,
                },
                "callback": latest_callback,
                "counts": {
                    "payloads": len(payloads),
                    "messageRows": len(messages),
                    "inbound": inbound_count,
                    "outbound": outbound_count,
                    "autoActions": len(actions),
                },
                "latestRequestText": compact_text(((latest_request_payload or {}).get("message") or {}).get("text"), 200),
                "latestAnswerText": compact_text(((latest_answer_payload or {}).get("message") or {}).get("text"), 200),
                "lastQuestion": (
                    {
                        "timestamp": str(last_question.get("timestamp") or "").strip() or None,
                        "text": compact_text(last_question.get("reply_text"), 240),
                    }
                    if last_question
                    else None
                ),
                "lastResult": (
                    {
                        "timestamp": str(last_result.get("timestamp") or "").strip() or None,
                        "text": compact_text(last_result.get("reply_text"), 240),
                    }
                    if last_result
                    else None
                ),
                "reportPath": str(latest_action.get("report_path") or "").strip() or None,
                "linkedRunIds": link_a2a_runs(known_runs, thread_id),
            }
        )

    items.sort(key=lambda item: item.get("updatedAt") or "", reverse=True)
    return items[: max(1, limit)]


HANDOFF_STATUSES = {"waiting_for_codex", "in_progress", "needs_reply", "done", "blocked"}


def base_handoff_inbox_state() -> dict[str, Any]:
    return {
        "version": 1,
        "updatedAt": now_iso(),
        "handoffsByOrg": {},
    }


def load_handoff_inbox_state() -> dict[str, Any]:
    state = read_json(HANDOFF_INBOX_PATH, base_handoff_inbox_state())
    if not isinstance(state, dict):
        return base_handoff_inbox_state()
    if "handoffsByOrg" not in state or not isinstance(state["handoffsByOrg"], dict):
        state["handoffsByOrg"] = {}
    return state


def save_handoff_inbox_state(state: dict[str, Any]) -> None:
    state["updatedAt"] = now_iso()
    write_json(HANDOFF_INBOX_PATH, state)


def normalized_handoff_status(value: Any, default: str = "waiting_for_codex") -> str:
    status = str(value or "").strip()
    return status if status in HANDOFF_STATUSES else default


def handoff_party(value: Any, *, default_agent: str, default_surface: str) -> dict[str, str | None]:
    row = value if isinstance(value, dict) else {}
    return {
        "agent": str(row.get("agent") or default_agent).strip() or default_agent,
        "surface": str(row.get("surface") or default_surface).strip() or default_surface,
        "host": str(row.get("host") or "").strip() or None,
    }


def handoff_source_thread(value: Any) -> dict[str, str | None]:
    row = value if isinstance(value, dict) else {}
    return {
        "channelId": str(row.get("channelId") or "").strip() or None,
        "threadId": str(row.get("threadId") or "").strip() or None,
        "channelName": str(row.get("channelName") or "").strip() or None,
        "threadName": str(row.get("threadName") or "").strip() or None,
        "url": str(row.get("url") or "").strip() or None,
    }


def create_handoff_item(payload: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    organization_id = str(payload.get("organizationId") or "").strip()
    if not organization_id:
        raise ValueError("organizationId is required")

    goal = str(payload.get("goal") or "").strip()
    if not goal:
        raise ValueError("goal is required")

    timestamp = now_iso()
    handoff_id = str(payload.get("id") or payload.get("handoffId") or f"handoff-{uuid.uuid4()}").strip()
    item = {
        "id": handoff_id,
        "kind": str(payload.get("kind") or "handoff_request").strip() or "handoff_request",
        "status": normalized_handoff_status(payload.get("status")),
        "createdAt": str(payload.get("createdAt") or timestamp).strip() or timestamp,
        "updatedAt": timestamp,
        "from": handoff_party(payload.get("from"), default_agent="desktop-hermes", default_surface="discord"),
        "to": handoff_party(payload.get("to"), default_agent="macbook-codex", default_surface="codex-app"),
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
    return organization_id, item


def list_handoff_items(organization_id: str, *, limit: int = DEFAULT_HANDOFF_LIMIT, status: str | None = None) -> list[dict[str, Any]]:
    state = load_handoff_inbox_state()
    rows = state.get("handoffsByOrg", {}).get(organization_id, [])
    if not isinstance(rows, list):
        return []
    items = [row for row in rows if isinstance(row, dict)]
    if status:
        items = [item for item in items if item.get("status") == status]
    items.sort(key=lambda item: str(item.get("updatedAt") or item.get("createdAt") or ""), reverse=True)
    return items[: max(1, limit)]


def update_handoff_status(payload: dict[str, Any], handoff_id: str) -> tuple[str, dict[str, Any]]:
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
        updated = {
            **item,
            "status": next_status,
            "updatedAt": now_iso(),
        }
        if "result" in payload:
            updated["result"] = compact_text(payload.get("result"), 1200)
        rows[index] = updated
        save_handoff_inbox_state(state)
        return organization_id, updated

    raise KeyError("Handoff not found")


def make_trace(agent_id: str, title: str, summary: str, tone: str) -> dict[str, Any]:
    return {
        "id": str(uuid.uuid4()),
        "timestamp": now_iso(),
        "agentId": agent_id,
        "title": title,
        "summary": summary,
        "tone": tone,
    }


def normalize_run_source(payload: Any) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None

    stream_id = str(payload.get("streamId") or "").strip()
    if not stream_id:
        return None

    source = {
        "streamId": stream_id,
        "channelId": str(payload.get("channelId") or "").strip() or None,
        "threadId": str(payload.get("threadId") or "").strip() or None,
        "channelName": str(payload.get("channelName") or "").strip() or None,
        "threadName": str(payload.get("threadName") or "").strip() or None,
    }
    return source


def branch_slug(value: str) -> str:
    out = []
    for ch in value.lower():
        if ch.isascii() and (ch.isalnum() or ch in {"-", "_"}):
            out.append(ch)
        else:
            out.append("-")
    slug = "".join(out).strip("-")
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug[:44] or "mission"


def github_repository() -> str | None:
    return env_value("AGENT_OS_GITHUB_REPO") or env_value("GITHUB_REPOSITORY")


def github_token() -> str | None:
    return env_value("AGENT_OS_GITHUB_TOKEN") or env_value("GITHUB_TOKEN") or env_value("GH_TOKEN")


def github_create_issues_enabled() -> bool:
    return is_enabled(env_value("AGENT_OS_GITHUB_CREATE_ISSUES"))


def github_create_pull_request_enabled() -> bool:
    return is_enabled(env_value("AGENT_OS_GITHUB_CREATE_PULL_REQUEST"))


def github_bootstrap_branch_enabled() -> bool:
    return is_enabled(env_value("AGENT_OS_GITHUB_BOOTSTRAP_BRANCH"))


def github_base_branch() -> str:
    return env_value("AGENT_OS_GITHUB_BASE_BRANCH") or "main"


def github_apply_labels_enabled() -> bool:
    return is_enabled(env_value("AGENT_OS_GITHUB_APPLY_LABELS"))


def encode_base64(value: str) -> str:
    return base64.b64encode(value.encode("utf-8")).decode("ascii")


def decode_base64(value: str) -> str:
    return base64.b64decode(value.replace("\n", "").encode("ascii")).decode("utf-8")


def slugify(value: str) -> str:
    out: list[str] = []
    last_dash = False
    for ch in value.lower():
        if ch.isascii() and (ch.isalnum() or ch == "_"):
            out.append(ch)
            last_dash = False
            continue
        if not last_dash:
            out.append("-")
            last_dash = True
    slug = "".join(out).strip("-")
    return slug[:80] or "run"


def encode_repo_path(path: str) -> str:
    return "/".join(quote(segment, safe="") for segment in path.split("/"))


def github_request(
    *,
    repository: str,
    token: str,
    path: str,
    method: str = "GET",
    body: Any | None = None,
    allow_not_found: bool = False,
) -> Any | None:
    url = f"https://api.github.com/repos/{repository}{path}"
    data = None
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")

    request = Request(url, method=method, headers=headers, data=data)
    try:
        with urlopen(request, timeout=20) as response:
            raw = response.read().decode("utf-8") or "null"
            return json.loads(raw)
    except HTTPError as exc:
        if exc.code == 404 and allow_not_found:
            return None
        message = exc.reason
        try:
            payload = json.loads(exc.read().decode("utf-8"))
            message = payload.get("message") or message
        except Exception:
            pass
        raise RuntimeError(f"GitHub request failed ({exc.code}): {message}") from exc
    except URLError as exc:
        raise RuntimeError(f"GitHub request failed: {exc.reason}") from exc


def find_artifact(run: dict[str, Any], kind: str) -> dict[str, Any] | None:
    return next((artifact for artifact in run["artifacts"] if artifact.get("kind") == kind), None)


def target_app_path() -> Path:
    configured = env_value("AGENT_OS_TARGET_APP_PATH")
    if configured:
        return Path(configured)
    return ROOT.parent / "physio_app"


def vercel_preview_enabled() -> bool:
    return is_enabled(env_value("AGENT_OS_VERCEL_PREVIEW_DEPLOY"))


def vercel_production_enabled() -> bool:
    return is_enabled(env_value("AGENT_OS_VERCEL_PRODUCTION_PROMOTE"))


def read_vercel_project_info() -> dict[str, Any] | None:
    project_file = target_app_path() / ".vercel" / "project.json"
    if not project_file.exists():
        return None
    try:
        data = json.loads(project_file.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    return data


def has_vercel_project_link() -> bool:
    info = read_vercel_project_info()
    return bool(info and info.get("projectName"))


def run_cli(command: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=False,
    )


def normalize_https_url(value: str | None) -> str | None:
    if not value:
        return None
    return value if value.startswith(("https://", "http://")) else f"https://{value}"


def parse_json_output(raw: str) -> Any | None:
    try:
        return json.loads(raw)
    except Exception:
        return None


def tail_lines(value: str, count: int = 18) -> str:
    lines = [line for line in value.splitlines() if line.strip()]
    return "\n".join(lines[-count:])


def build_base_run(
    *,
    title: str,
    description: str,
    lane_id: str,
    priority: str = "medium",
    status: str = "waiting-for-approval",
    workflow_ids: list[str] | None = None,
    owner_agents: list[str] | None = None,
    approval_gates: list[str] | None = None,
    artifacts: list[dict[str, Any]] | None = None,
    trace_items: list[dict[str, Any]] | None = None,
    source: dict[str, Any] | None = None,
) -> dict[str, Any]:
    lane = LANES.get(lane_id)
    if not lane:
        raise ValueError(f"Unknown laneId: {lane_id}")

    run_id = str(uuid.uuid4())
    created_at = now_iso()
    gates = approval_gates if approval_gates is not None else list(lane["approvalGates"])
    run_workflows = workflow_ids if workflow_ids is not None else list(lane["defaultWorkflowIds"])
    run_agents = owner_agents if owner_agents is not None else list(lane["primaryAgents"])
    approval_items = []
    for index, gate in enumerate(gates):
        approval_items.append(
            {
                "id": str(uuid.uuid4()),
                "gate": gate,
                "label": approval_label(gate),
                "status": "pending" if index == 0 else "waived",
                "requiredBy": default_approval_agent(gate),
            }
        )

    base_artifacts = [
        {"label": "Lane", "value": lane["name"]},
        {"label": "Target green level", "value": lane["defaultGreenLevel"]},
        {"label": "Primary agents", "value": ", ".join(run_agents)},
    ]
    if source and source.get("streamId"):
        base_artifacts.append({"label": "Source stream", "value": str(source["streamId"])})
    if source and source.get("threadName"):
        base_artifacts.append({"label": "Source thread", "value": str(source["threadName"])})
    if source and source.get("channelName"):
        base_artifacts.append({"label": "Source channel", "value": str(source["channelName"])})
    if artifacts:
        base_artifacts.extend(artifacts)

    base_trace = trace_items or [
        make_trace(
            "orchestrator",
            "Mission received",
            f"{lane['name']} selected with {lane['defaultGreenLevel']} green-level target.",
            "neutral",
        ),
        make_trace(
            "planner",
            f"{approval_label(gates[0]) if gates else 'Approval'} requested",
            "Human approval is required before the next stage can continue.",
            "warning",
        ),
    ]

    return {
        "id": run_id,
        "title": title,
        "description": description,
        "laneId": lane_id,
        "status": status,
        "priority": priority,
        "workflowIds": run_workflows,
        "ownerAgents": run_agents,
        "approvalItems": approval_items,
        "traceItems": base_trace,
        "artifacts": base_artifacts,
        "source": source,
        "createdAt": created_at,
        "updatedAt": created_at,
    }


def create_issue_draft_artifacts(run: dict[str, Any]) -> list[dict[str, Any]]:
    lane = LANES[run["laneId"]]
    prd_value = "\n".join(
        [
            f"# {run['title']}",
            "",
            "## Goal",
            run["description"],
            "",
            "## Operating Lane",
            f"{lane['label']} / {lane['name']}",
            "",
            "## Primary Agents",
            ", ".join(run["ownerAgents"]),
            "",
            "## Approval Gates",
            "\n".join(
                [
                    f"- {item['label']}: {item['status']}"
                    for item in run["approvalItems"]
                ]
            ),
        ]
    )
    issue_title = f"[Planner] PRD and task split: {run['title']}"
    issue_body = "\n".join(
        [
            "## Mission",
            run["title"],
            "",
            "## Problem",
            run["description"],
            "",
            "## Scope",
            "- PRD 초안 작성",
            "- frontend/backend/DB/QA/DevOps 작업 분리",
            "- 명시적인 approval boundary 정의",
            "",
            "## Acceptance Criteria",
            "- [ ] 작업 범위와 제외 범위가 issue 본문에 있다.",
            "- [ ] approval gate가 Mission Control에 남아 있다.",
            "- [ ] 검증 기준이 green level과 명령어 기준으로 기록된다.",
            "",
            "## Harness",
            f"- Lane: {run['laneId']}",
            f"- Priority: {run['priority']}",
            f"- Source run: {run['id']}",
        ]
    )
    return [
        {
            "label": "PRD Draft",
            "kind": "prd",
            "value": prd_value,
            "metadata": {"laneId": run["laneId"], "workflow": "prd-to-issue"},
        },
        {
            "label": f"Issue Draft 1: {issue_title}",
            "kind": "issue-draft",
            "value": issue_body,
            "metadata": {
                "title": issue_title,
                "labels": f"agent-os,planner,lane:{run['laneId']}",
                "ownerAgent": "planner",
                "issueKind": "prd",
            },
        },
    ]


def create_issue_to_pr_artifacts(run: dict[str, Any]) -> list[dict[str, Any]]:
    branch_name = f"codex/agent-os-{branch_slug(run['title'])}"
    base_branch = github_base_branch()
    pr_body = "\n".join(
        [
            "## Summary",
            f"Implements the approved Mission Control run: {run['title']}.",
            "",
            "## Branch",
            branch_name,
            "",
            "## Testing",
            "- [ ] pnpm run typecheck",
            "- [ ] pnpm exec eslint <changed-files>",
            "- [ ] Preview smoke",
            "",
            "## Risk Notes",
            "- Keep changes inside the selected agent permission boundary.",
            "- Record waived checks explicitly before requesting review.",
            "- Do not deploy production until preview and production gates are approved.",
        ]
    )
    return [
        {
            "label": "Issue To PR Plan",
            "kind": "issue-to-pr-plan",
            "value": "\n".join(
                [
                    f"Primary worker: {run['ownerAgents'][0] if run['ownerAgents'] else 'orchestrator'}",
                    "Target issues: 1",
                    f"Branch: {branch_name}",
                    "",
                    "Context pack:",
                    "- docs/CANONICAL_DOCS.md",
                    "- docs/ARCHITECTURE_RULES.md",
                    "- docs/SYSTEM_ARCHITECTURE.md",
                ]
            ),
            "metadata": {
                "branchName": branch_name,
                "primaryAgent": run["ownerAgents"][0] if run["ownerAgents"] else "orchestrator",
                "targetIssueCount": 1,
            },
        },
        {
            "label": "Branch Plan",
            "kind": "branch-plan",
            "value": "\n".join(
                [
                    f"git switch -c {branch_name}",
                    "",
                    "Worker start condition:",
                    "- clean/understood worktree state",
                    "- selected target issue",
                    "- permission profile loaded",
                ]
            ),
            "metadata": {"branchName": branch_name},
        },
        {
            "label": "Check Plan",
            "kind": "check-plan",
            "value": "- pnpm run typecheck\n- pnpm exec eslint <changed-files>\n- preview smoke",
            "metadata": {"checks": "pnpm run typecheck | pnpm exec eslint <changed-files> | preview smoke"},
        },
        {
            "label": "Draft PR Payload",
            "kind": "pr-draft",
            "value": pr_body,
            "metadata": {
                "title": f"[Agent OS] {run['title']}",
                "branchName": branch_name,
                "baseBranch": base_branch,
                "dryRun": True,
            },
        },
    ]


def create_worker_pr_artifacts(run: dict[str, Any]) -> list[dict[str, Any]]:
    branch_name = f"codex/agent-os-{branch_slug(run['title'])}"
    base_branch = github_base_branch()
    pr_url = f"https://github.com/Youngkwon-Lee/physio_app/pull/{abs(hash(run['id'])) % 9000 + 1000}"
    return [
        {
            "label": "Worker Run",
            "kind": "worker-run",
            "value": "\n".join(
                [
                    "Mode: dry-run",
                    f"Branch: {branch_name}",
                    "",
                    "Command plan:",
                    f"- git switch -c {branch_name}",
                    "- load docs/CANONICAL_DOCS.md",
                    "- implement inside writable path boundary",
                    "- record changed files and risks",
                ]
            ),
            "metadata": {"dryRun": True, "branchName": branch_name},
        },
        {
            "label": "Permission Audit",
            "kind": "permission-audit",
            "value": "\n".join(
                [
                    "Writable:",
                    "- src/features/**",
                    "- src/components/**",
                    "",
                    "Approval required:",
                    "- pull-request",
                    "- preview",
                    "",
                    "Forbidden:",
                    "- billing",
                    "- auth",
                    "- unapproved DB schema changes",
                ]
            ),
            "metadata": {"profile": "mission-control-worker"},
        },
        {
            "label": "Check Result",
            "kind": "check-result",
            "value": "\n".join(
                [
                    "Mode: dry-run",
                    "Planned checks:",
                    "- pnpm run typecheck",
                    "- pnpm exec eslint <changed-files>",
                    "- preview smoke",
                    "",
                    "Dry-run only. No repository files were changed by this API.",
                ]
            ),
            "metadata": {"dryRun": True},
        },
        {
            "label": "Pull Request Payload",
            "kind": "pull-request",
            "value": "\n".join(
                [
                    "## Summary",
                    f"Draft PR prepared for {run['title']}.",
                    "",
                    "## Status",
                    "Dry-run payload only. Human review still required before publish.",
                    "",
                    f"Suggested URL: {pr_url}",
                ]
            ),
            "metadata": {
                "dryRun": True,
                "title": f"[Agent OS] {run['title']}",
                "branchName": branch_name,
                "baseBranch": base_branch,
                "pullRequestUrl": pr_url,
            },
        },
    ]


def create_github_issue_payloads(run: dict[str, Any]) -> list[dict[str, Any]]:
    payloads = []
    for artifact in run["artifacts"]:
        if artifact.get("kind") != "issue-draft":
            continue
        labels = [
            label.strip()
            for label in str(artifact.get("metadata", {}).get("labels", "")).split(",")
            if label.strip()
        ]
        payloads.append(
            {
                "title": str(artifact.get("metadata", {}).get("title") or artifact.get("label") or "Issue Draft"),
                "body": "\n".join(
                    [
                        str(artifact.get("value") or ""),
                        "",
                        "---",
                        "Generated by Mission Control.",
                        f"Run: {run['id']}",
                    ]
                ),
                "labels": labels,
            }
        )
    return payloads


def create_github_pull_request_payload(run: dict[str, Any]) -> dict[str, Any]:
    artifact = find_artifact(run, "pull-request") or find_artifact(run, "pr-draft") or {}
    metadata = artifact.get("metadata", {})
    title = str(metadata.get("title") or f"[Agent OS] {run['title']}")
    head = str(metadata.get("branchName") or f"codex/agent-os-{run['id']}")
    base = str(metadata.get("baseBranch") or github_base_branch())
    body = "\n".join(
        [
            str(artifact.get("value") or f"Implements Mission Control run {run['id']}."),
            "",
            "---",
            "Generated by Mission Control.",
            f"Run: {run['id']}",
        ]
    )
    return {
        "title": title,
        "head": head,
        "base": base,
        "draft": True,
        "body": body,
    }


def create_run_snapshot_markdown(run: dict[str, Any], payload: dict[str, Any]) -> str:
    pending = next((item for item in run["approvalItems"] if item["status"] == "pending"), None)
    artifact_lines = [
        f"- {artifact.get('kind') or 'artifact'}: {artifact.get('label') or 'Untitled'}"
        for artifact in run["artifacts"]
    ]
    trace_lines = [
        f"- {trace.get('timestamp')} / {trace.get('agentId')} / {trace.get('title')}: {trace.get('summary')}"
        for trace in run["traceItems"][-10:]
    ]
    return "\n".join(
        [
            f"# {run['title']}",
            "",
            "## Mission",
            run["description"],
            "",
            "## Run State",
            f"- Run: {run['id']}",
            f"- Lane: {run['laneId']}",
            f"- Status: {run['status']}",
            f"- Priority: {run['priority']}",
            f"- Pending gate: {pending.get('gate') if pending else 'none'}",
            f"- PR branch: {payload['head']}",
            "",
            "## Owner Agents",
            "\n".join(f"- {agent}" for agent in run["ownerAgents"]) or "- none",
            "",
            "## Artifacts",
            "\n".join(artifact_lines) or "- none",
            "",
            "## Recent Trace",
            "\n".join(trace_lines) or "- none",
            "",
            "## Draft PR Body",
            payload["body"],
        ]
    )


def create_vercel_json_patch(current_content: str, run: dict[str, Any]) -> str | None:
    cron_artifact = next(
        (
            artifact for artifact in run["artifacts"]
            if artifact.get("metadata", {}).get("file") == "vercel.json"
            and isinstance(artifact.get("metadata", {}).get("path"), str)
            and isinstance(artifact.get("metadata", {}).get("schedule"), str)
        ),
        None,
    )
    if not cron_artifact:
        return None

    parsed = json.loads(current_content)
    if not isinstance(parsed, dict):
        parsed = {}
    existing_crons = parsed.get("crons") if isinstance(parsed.get("crons"), list) else []
    cron_entry = {
        "path": str(cron_artifact["metadata"]["path"]),
        "schedule": str(cron_artifact["metadata"]["schedule"]),
    }
    has_entry = any(isinstance(item, dict) and item.get("path") == cron_entry["path"] for item in existing_crons)
    next_crons = []
    for item in existing_crons:
        if isinstance(item, dict) and item.get("path") == cron_entry["path"]:
            next_crons.append({**item, **cron_entry})
        else:
            next_crons.append(item)
    if not has_entry:
        next_crons.append(cron_entry)

    parsed["crons"] = next_crons
    return json.dumps(parsed, ensure_ascii=False, indent=2) + "\n"


def get_github_file(*, repository: str, token: str, path: str, branch: str) -> dict[str, Any] | None:
    return github_request(
        repository=repository,
        token=token,
        path=f"/contents/{encode_repo_path(path)}?ref={quote(branch, safe='')}",
        allow_not_found=True,
    )


def put_github_file(
    *,
    repository: str,
    token: str,
    path: str,
    branch: str,
    content: str,
    message: str,
) -> None:
    current = get_github_file(repository=repository, token=token, path=path, branch=branch)
    body: dict[str, Any] = {
        "message": message,
        "content": encode_base64(content),
        "branch": branch,
    }
    if isinstance(current, dict) and current.get("sha"):
        body["sha"] = current["sha"]
    github_request(
        repository=repository,
        token=token,
        path=f"/contents/{encode_repo_path(path)}",
        method="PUT",
        body=body,
    )


def ensure_github_branch(*, repository: str, token: str, base_branch: str, head_branch: str) -> dict[str, Any]:
    branch_ref = github_request(
        repository=repository,
        token=token,
        path=f"/git/ref/heads/{encode_repo_path(head_branch)}",
        allow_not_found=True,
    )
    if isinstance(branch_ref, dict) and isinstance(branch_ref.get("object"), dict) and branch_ref["object"].get("sha"):
        return {"created": False, "sha": branch_ref["object"]["sha"]}

    base_ref = github_request(
        repository=repository,
        token=token,
        path=f"/git/ref/heads/{encode_repo_path(base_branch)}",
    )
    base_sha = (
        base_ref.get("object", {}).get("sha")
        if isinstance(base_ref, dict)
        else None
    )
    if not isinstance(base_sha, str) or not base_sha:
        raise RuntimeError(f"Could not resolve base branch {base_branch}")

    github_request(
        repository=repository,
        token=token,
        path="/git/refs",
        method="POST",
        body={"ref": f"refs/heads/{head_branch}", "sha": base_sha},
    )
    return {"created": True, "sha": base_sha}


def bootstrap_worker_branch(*, repository: str, token: str, run: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    branch = ensure_github_branch(
        repository=repository,
        token=token,
        base_branch=payload["base"],
        head_branch=payload["head"],
    )
    run_snapshot_path = f"docs/agent-os/runs/{slugify(run['id'])}.md"
    changed_files = [run_snapshot_path]
    put_github_file(
        repository=repository,
        token=token,
        path=run_snapshot_path,
        branch=payload["head"],
        content=create_run_snapshot_markdown(run, payload),
        message=f"chore(agent-os): add run snapshot for {run['id']}",
    )

    vercel_json_file = get_github_file(
        repository=repository,
        token=token,
        path="vercel.json",
        branch=payload["head"],
    )
    if (
        isinstance(vercel_json_file, dict)
        and vercel_json_file.get("content")
        and vercel_json_file.get("encoding") == "base64"
    ):
        next_vercel_json = create_vercel_json_patch(decode_base64(str(vercel_json_file["content"])), run)
        if next_vercel_json:
            put_github_file(
                repository=repository,
                token=token,
                path="vercel.json",
                branch=payload["head"],
                content=next_vercel_json,
                message="chore(agent-os): enable heartbeat cron proposal",
            )
            changed_files.append("vercel.json")

    return {"branchCreated": branch["created"], "changedFiles": changed_files}


def publish_issue_drafts(run: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    payloads = create_github_issue_payloads(run)
    repository = github_repository()
    token = github_token()
    dry_run_reason = (
        "Missing AGENT_OS_GITHUB_REPO or GITHUB_REPOSITORY."
        if not repository
        else "Missing AGENT_OS_GITHUB_TOKEN, GITHUB_TOKEN, or GH_TOKEN."
        if not token
        else "AGENT_OS_GITHUB_CREATE_ISSUES is not enabled."
        if not github_create_issues_enabled()
        else None
    )
    traces: list[dict[str, Any]] = []
    artifacts: list[dict[str, Any]] = []

    if dry_run_reason:
        for index, payload in enumerate(payloads, start=1):
            artifacts.append(
                {
                    "label": f"GitHub Issue Payload {index}",
                    "kind": "github-issue",
                    "value": payload["title"],
                    "metadata": {
                        "title": payload["title"],
                        "issueNumber": None,
                        "issueUrl": None,
                        "dryRun": True,
                        "reason": dry_run_reason,
                    },
                }
            )
        traces.append(
            make_trace(
                "planner",
                "GitHub issue publish stayed in dry-run",
                dry_run_reason,
                "warning",
            )
        )
        return artifacts, traces

    for payload in payloads:
        body: dict[str, Any] = {"title": payload["title"], "body": payload["body"]}
        if github_apply_labels_enabled() and payload["labels"]:
            body["labels"] = payload["labels"]
        result = github_request(
            repository=repository,
            token=token,
            path="/issues",
            method="POST",
            body=body,
        ) or {}
        artifacts.append(
            {
                "label": f"GitHub Issue #{result.get('number') or payload['title']}",
                "kind": "github-issue",
                "value": str(result.get("html_url") or payload["title"]),
                "metadata": {
                    "title": payload["title"],
                    "issueNumber": result.get("number"),
                    "issueUrl": result.get("html_url"),
                    "dryRun": False,
                },
            }
        )
    traces.append(
        make_trace(
            "planner",
            "GitHub issues published",
            f"{len(artifacts)} issue payloads were created in {repository}.",
            "success",
        )
    )
    return artifacts, traces


def publish_pull_request(run: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    repository = github_repository()
    token = github_token()
    payload = create_github_pull_request_payload(run)
    dry_run_reason = (
        "Missing AGENT_OS_GITHUB_REPO or GITHUB_REPOSITORY."
        if not repository
        else "Missing AGENT_OS_GITHUB_TOKEN, GITHUB_TOKEN, or GH_TOKEN."
        if not token
        else "AGENT_OS_GITHUB_CREATE_PULL_REQUEST is not enabled."
        if not github_create_pull_request_enabled()
        else "AGENT_OS_GITHUB_BOOTSTRAP_BRANCH is not enabled."
        if not github_bootstrap_branch_enabled()
        else None
    )
    traces: list[dict[str, Any]] = []
    artifacts: list[dict[str, Any]] = []

    if dry_run_reason:
        artifacts.append(
            {
                "label": "GitHub Pull Request Payload",
                "kind": "pull-request",
                "value": "\n".join(
                    [
                        f"Title: {payload['title']}",
                        f"Head: {payload['head']}",
                        f"Base: {payload['base']}",
                        f"Draft: {payload['draft']}",
                        f"Reason: {dry_run_reason}",
                    ]
                ),
                "metadata": {
                    "title": payload["title"],
                    "baseBranch": payload["base"],
                    "pullRequestNumber": None,
                    "pullRequestUrl": None,
                    "dryRun": True,
                    "reason": dry_run_reason,
                    "branchName": payload["head"],
                    "branchCreated": False,
                    "changedFiles": "",
                },
            }
        )
        traces.append(
            make_trace(
                "orchestrator",
                "GitHub PR publish stayed in dry-run",
                dry_run_reason,
                "warning",
            )
        )
        return artifacts, traces

    bootstrap_result = bootstrap_worker_branch(
        repository=repository,
        token=token,
        run=run,
        payload=payload,
    )
    branch_created = bool(bootstrap_result["branchCreated"])
    changed_files = list(bootstrap_result["changedFiles"])

    repository_owner = repository.split("/")[0]
    head_ref = quote(f"{repository_owner}:{payload['head']}", safe="")
    base_ref = quote(payload["base"], safe="")
    existing_pulls = github_request(
        repository=repository,
        token=token,
        path=f"/pulls?state=open&head={head_ref}&base={base_ref}",
    ) or []
    existing_pull = existing_pulls[0] if isinstance(existing_pulls, list) and existing_pulls else None

    if isinstance(existing_pull, dict):
        result = {
            "number": existing_pull.get("number"),
            "html_url": existing_pull.get("html_url"),
            "title": existing_pull.get("title") or payload["title"],
            "reason": "Existing open PR reused.",
        }
    else:
        result = github_request(
            repository=repository,
            token=token,
            path="/pulls",
            method="POST",
            body=payload,
        ) or {}
        result["reason"] = None

    artifacts.append(
        {
            "label": f"GitHub Pull Request #{result.get('number') or '-'}",
            "kind": "pull-request",
            "value": str(result.get("html_url") or payload["title"]),
            "metadata": {
                "title": payload["title"],
                "baseBranch": payload["base"],
                "pullRequestNumber": result.get("number"),
                "pullRequestUrl": result.get("html_url"),
                "dryRun": False,
                "reason": result.get("reason"),
                "branchName": payload["head"],
                "branchCreated": branch_created,
                "changedFiles": " | ".join(changed_files),
            },
        }
    )
    traces.append(
        make_trace(
            "orchestrator",
            "GitHub draft PR published",
            f"Draft PR is ready in {repository} on branch {payload['head']}.",
            "success",
        )
    )
    return artifacts, traces


def latest_live_pull_request_artifact(run: dict[str, Any]) -> dict[str, Any] | None:
    for artifact in reversed(run["artifacts"]):
        if artifact.get("kind") == "pull-request" and not artifact.get("metadata", {}).get("dryRun"):
            return artifact
    return None


def preview_hold_trace(state: str) -> dict[str, Any]:
    if state == "ready":
        return make_trace(
            "devops",
            "Production gate unlocked",
            "Preview is ready. Production approval can continue when the operator decides.",
            "success",
        )
    if state == "building":
        return make_trace(
            "devops",
            "Production gate held",
            "Preview is still building. Production approval stays locked until preview is ready.",
            "warning",
        )
    return make_trace(
        "devops",
        "Production gate held",
        "Preview is not healthy. Production approval stays locked until the preview problem is fixed.",
        "danger",
    )


def publish_preview_deployment(run: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], str]:
    app_path = target_app_path()
    project = read_vercel_project_info()
    pull_request_artifact = latest_live_pull_request_artifact(run)
    pull_request_number = (
        pull_request_artifact.get("metadata", {}).get("pullRequestNumber")
        if pull_request_artifact
        else None
    )
    branch_name = (
        str(pull_request_artifact.get("metadata", {}).get("branchName"))
        if pull_request_artifact and pull_request_artifact.get("metadata", {}).get("branchName")
        else None
    )
    dry_run_reason = (
        "AGENT_OS_VERCEL_PREVIEW_DEPLOY is not enabled."
        if not vercel_preview_enabled()
        else f"Mission Control target app path does not exist: {app_path}"
        if not app_path.exists()
        else "Missing .vercel/project.json link for the target app."
        if not project
        else "Live pull request metadata is missing."
        if not pull_request_number and not branch_name
        else None
    )

    if dry_run_reason:
        return (
            [
                {
                    "label": "Preview Deployment",
                    "kind": "preview-deploy",
                    "value": "\n".join(
                        [
                            "Mode: dry-run",
                            dry_run_reason,
                        ]
                    ),
                    "metadata": {"dryRun": True, "state": "dry-run"},
                }
            ],
            [
                make_trace(
                    "devops",
                    "Preview deploy stayed in dry-run",
                    dry_run_reason,
                    "warning",
                )
            ],
            "dry-run",
        )

    project_name = str(project.get("projectName"))
    command = ["vercel", "list", project_name, "--format", "json"]
    if pull_request_number:
        command.extend(["--meta", f"githubPrId={pull_request_number}"])
    elif branch_name:
        command.extend(["--meta", f"githubCommitRef={branch_name}"])

    list_result = run_cli(command, cwd=app_path)
    if list_result.returncode != 0:
        raise RuntimeError(list_result.stderr.strip() or list_result.stdout.strip() or "Failed to list Vercel deployments.")

    payload = parse_json_output(list_result.stdout) or {}
    deployments = payload.get("deployments") if isinstance(payload, dict) else None
    if not isinstance(deployments, list) or not deployments:
        return (
            [
                {
                    "label": "Preview Deployment",
                    "kind": "preview-deploy",
                    "value": "No Vercel preview deployment was found for this PR yet.",
                    "metadata": {"dryRun": False, "state": "building"},
                }
            ],
            [
                make_trace(
                    "devops",
                    "Preview deployment not found yet",
                    "Vercel has not exposed a deployment for this PR yet. Check again after the Git integration finishes.",
                    "warning",
                )
            ],
            "building",
        )

    def deployment_rank(item: dict[str, Any]) -> tuple[int, int]:
        created = int(item.get("createdAt") or 0)
        state = str(item.get("state") or "")
        state_rank = 2 if state == "READY" else 1 if state in {"BUILDING", "QUEUED"} else 0
        return (state_rank, created)

    deployment = sorted(
        [item for item in deployments if isinstance(item, dict)],
        key=deployment_rank,
        reverse=True,
    )[0]
    meta = deployment.get("meta", {}) if isinstance(deployment.get("meta"), dict) else {}
    deployment_url = normalize_https_url(str(deployment.get("url") or "")) or ""
    branch_alias = normalize_https_url(str(meta.get("branchAlias") or "")) or None
    preview_url = branch_alias or deployment_url
    state = str(deployment.get("state") or "UNKNOWN").upper()
    state_label = {
        "READY": "ready",
        "INITIALIZING": "building",
        "BUILDING": "building",
        "QUEUED": "building",
        "ERROR": "error",
        "CANCELED": "error",
    }.get(state, "error")

    logs_excerpt = ""
    if state != "READY":
        inspect_result = run_cli(["vercel", "inspect", deployment_url, "--logs"], cwd=app_path)
        logs_excerpt = tail_lines((inspect_result.stdout or "").strip() or (inspect_result.stderr or "").strip())

    artifacts = [
        {
            "label": "Preview Deployment",
            "kind": "preview-deploy",
            "value": "\n".join(
                [
                    f"State: {state}",
                    f"Preview URL: {preview_url}",
                    f"Deployment URL: {deployment_url}",
                    f"Branch: {meta.get('githubCommitRef') or branch_name or '-'}",
                ]
            ),
            "metadata": {
                "dryRun": False,
                "previewUrl": preview_url,
                "deploymentUrl": deployment_url,
                "branchAlias": branch_alias,
                "branchName": str(meta.get("githubCommitRef") or branch_name or ""),
                "pullRequestNumber": pull_request_number,
                "state": state,
            },
        },
        {
            "label": "Preview Smoke Report",
            "kind": "smoke-report",
            "value": (
                "\n".join(
                    [
                        f"State: {state}",
                        "Git preview is ready.",
                        f"Open: {preview_url}",
                        "Next: verify the changed route and auth path before production.",
                    ]
                )
                if state == "READY"
                else "\n".join(
                    [
                        f"State: {state}",
                        f"Open: {preview_url}",
                        "",
                        "Recent build log:",
                        logs_excerpt or "No log excerpt was captured.",
                    ]
                )
            ),
            "metadata": {
                "dryRun": state != "READY",
                "previewUrl": preview_url,
                "state": state,
            },
        },
        {
            "label": "Rollback Plan",
            "kind": "rollback-plan",
            "value": (
                "- Close the broken PR preview by pushing a fix branch update\n"
                "- Wait for the next Vercel Git preview\n"
                "- Keep production gate locked until preview is healthy"
            ),
            "metadata": {"previewUrl": preview_url, "state": state},
        },
        {
            "label": "Monitoring Plan",
            "kind": "monitoring-plan",
            "value": (
                "- Watch GitHub checks and Vercel deployment state\n"
                "- Verify preview route, auth redirect, and console errors\n"
                "- Only unlock production when the preview status is READY"
            ),
            "metadata": {"previewUrl": preview_url, "state": state},
        },
    ]
    traces = [
        make_trace(
            "devops",
            "Preview deployment ready" if state == "READY" else "Preview deployment failed" if state == "ERROR" else "Preview deployment in progress",
            (
                f"Preview is live at {preview_url}."
                if state == "READY"
                else logs_excerpt.splitlines()[-1]
                if logs_excerpt
                else f"Vercel reported {state} for the current preview deployment."
            ),
            "success" if state == "READY" else "danger" if state == "ERROR" else "warning",
        )
    ]
    return artifacts, traces, state_label


def attach_publish_result(
    run: dict[str, Any],
    *,
    publisher: str,
    publish_fn: Any,
) -> None:
    try:
        artifacts, traces = publish_fn(run)
    except Exception as exc:
        run["traceItems"].append(
            make_trace(
                publisher,
                "External publish failed",
                str(exc),
                "danger",
            )
        )
        run["artifacts"].append(
            {
                "label": f"{publisher} publish error",
                "kind": "integration-error",
                "value": str(exc),
                "metadata": {"publisher": publisher},
            }
        )
        return

    append_unique_artifacts(run, artifacts)
    run["traceItems"].extend(traces)


def attach_preview_publish_result(run: dict[str, Any]) -> str:
    try:
        artifacts, traces, state = publish_preview_deployment(run)
    except Exception as exc:
        run["traceItems"].append(
            make_trace(
                "devops",
                "Preview publish failed",
                str(exc),
                "danger",
            )
        )
        run["artifacts"].append(
            {
                "label": "Preview deploy error",
                "kind": "monitoring-plan",
                "value": str(exc),
                "metadata": {"state": "ERROR"},
            }
        )
        return "error"

    replace_or_append_artifacts(run, artifacts)
    run["traceItems"].extend(traces)
    return state


def create_preview_artifacts(run: dict[str, Any]) -> list[dict[str, Any]]:
    branch_name = f"codex-agent-os-{branch_slug(run['title'])}"
    preview_url = f"https://{branch_name}.vercel.app"
    return [
        {
            "label": "Preview Deployment",
            "kind": "preview-deploy",
            "value": "\n".join(
                [
                    "Mode: dry-run",
                    f"Branch: {branch_name}",
                    f"Preview URL: {preview_url}",
                    "",
                    "Command plan:",
                    "- vercel deploy --prebuilt",
                    "- vercel inspect <preview-url>",
                    "- attach deployment URL and build status to this run",
                ]
            ),
            "metadata": {"dryRun": True, "branchName": branch_name, "previewUrl": preview_url},
        },
        {
            "label": "Preview Smoke Report",
            "kind": "smoke-report",
            "value": "\n".join(
                [
                    "Mode: dry-run",
                    "Smoke checklist:",
                    "- preview URL responds with 2xx",
                    "- changed route renders without console/page errors",
                    "- auth redirect behavior is intact",
                    "- no obvious mobile/desktop overlap",
                ]
            ),
            "metadata": {"dryRun": True, "previewUrl": preview_url},
        },
        {
            "label": "Rollback Plan",
            "kind": "rollback-plan",
            "value": "- vercel rollback\n- remove bad preview\n- restore previous promote candidate",
            "metadata": {"previewUrl": preview_url},
        },
        {
            "label": "Monitoring Plan",
            "kind": "monitoring-plan",
            "value": "- watch Vercel runtime logs\n- check error rate\n- check first user path after promote",
            "metadata": {"previewUrl": preview_url},
        },
    ]


def create_production_artifacts(run: dict[str, Any]) -> list[dict[str, Any]]:
    preview = next((item for item in run["artifacts"] if item.get("kind") == "preview-deploy"), None)
    preview_url = (preview or {}).get("metadata", {}).get("previewUrl") or f"https://preview-{run['id']}.vercel.app"
    return [
        {
            "label": "Production Deploy Payload",
            "kind": "production-deploy",
            "value": "\n".join(
                [
                    "Mode: dry-run",
                    f"Validated preview: {preview_url}",
                    "",
                    "Command plan:",
                    f"- vercel promote {preview_url}",
                    "- verify production alias",
                    "- start monitoring window",
                ]
            ),
            "metadata": {"dryRun": True, "previewUrl": preview_url, "productionUrl": env_value("AGENT_OS_PRODUCTION_URL")},
        },
        {
            "label": "Release Note",
            "kind": "release-note",
            "value": "\n".join(
                [
                    f"Released mission: {run['title']}",
                    "",
                    "Post-release owner:",
                    "- DevOps Agent monitors runtime logs",
                    "- QA Agent validates smoke path",
                    "- Orchestrator opens rollback gate if monitoring fails",
                ]
            ),
            "metadata": {"previewUrl": preview_url},
        },
    ]


def append_unique_artifacts(run: dict[str, Any], artifacts: list[dict[str, Any]]) -> None:
    existing_keys = {(item.get("kind"), item.get("label")) for item in run["artifacts"]}
    for artifact in artifacts:
        key = (artifact.get("kind"), artifact.get("label"))
        if key in existing_keys:
            continue
        run["artifacts"].append(artifact)
        existing_keys.add(key)


def replace_or_append_artifacts(run: dict[str, Any], artifacts: list[dict[str, Any]]) -> None:
    for artifact in artifacts:
        key = (artifact.get("kind"), artifact.get("label"))
        replaced = False
        for index, current in enumerate(run["artifacts"]):
            current_key = (current.get("kind"), current.get("label"))
            if current_key == key:
                run["artifacts"][index] = artifact
                replaced = True
                break
        if not replaced:
            run["artifacts"].append(artifact)


def update_run_after_approval(run: dict[str, Any], gate: str) -> None:
    if gate == "plan" and "prd-to-issue" in run["workflowIds"]:
        append_unique_artifacts(run, create_issue_draft_artifacts(run))
        run["traceItems"].append(
            make_trace(
                "planner",
                "PRD and issue drafts prepared",
                "PRD draft and issue draft payloads are attached for review.",
                "success",
            )
        )
    elif gate == "issue" and "issue-to-pr" in run["workflowIds"]:
        append_unique_artifacts(run, create_issue_to_pr_artifacts(run))
        run["traceItems"].append(
            make_trace(
                "orchestrator",
                "Issue To PR plan prepared",
                "Branch plan, check plan, and PR draft payload are ready.",
                "success",
            )
        )
        attach_publish_result(run, publisher="planner", publish_fn=publish_issue_drafts)
    elif gate == "pull-request":
        append_unique_artifacts(run, create_worker_pr_artifacts(run))
        run["traceItems"].append(
            make_trace(
                "orchestrator",
                "Worker adapter prepared",
                "Dry-run worker command plan, permission audit, checks, and PR payload are attached.",
                "success",
            )
        )
        attach_publish_result(run, publisher="orchestrator", publish_fn=publish_pull_request)
    elif gate == "preview":
        append_unique_artifacts(run, create_preview_artifacts(run))
        run["traceItems"].append(
            make_trace(
                "devops",
                "Preview deploy package prepared",
                "Preview deployment, smoke report, rollback plan, and monitoring plan are attached.",
                "success",
            )
        )
        preview_state = attach_preview_publish_result(run)
        if preview_state != "ready":
            production_gate = next(
                (item for item in run["approvalItems"] if item["gate"] == "production" and item["status"] == "pending"),
                None,
            )
            if production_gate:
                production_gate["status"] = "locked"
            run["status"] = "blocked"
            run["traceItems"].append(preview_hold_trace(preview_state))
    elif gate == "production":
        append_unique_artifacts(run, create_production_artifacts(run))
        run["traceItems"].append(
            make_trace(
                "devops",
                "Production deploy payload prepared",
                "Production promote payload and release note are attached.",
                "success",
            )
        )


def approve_next_pending_gate(run: dict[str, Any]) -> dict[str, Any]:
    pending_index = next((index for index, item in enumerate(run["approvalItems"]) if item["status"] == "pending"), -1)
    if pending_index < 0:
        return run

    run = deepcopy(run)
    current = run["approvalItems"][pending_index]
    current["status"] = "approved"
    next_pending = run["approvalItems"][pending_index + 1] if pending_index + 1 < len(run["approvalItems"]) else None
    if next_pending and next_pending["status"] == "waived":
        next_pending["status"] = "pending"
    run["status"] = "waiting-for-approval" if any(item["status"] == "pending" for item in run["approvalItems"]) else "completed"
    run["updatedAt"] = now_iso()
    run["traceItems"].append(
        make_trace(
            current["requiredBy"],
            f"{current['label']} approved",
            f"{next_pending['label']} is now the next human gate." if next_pending else "All human gates are complete.",
            "success",
        )
    )
    update_run_after_approval(run, current["gate"])
    return run


def reject_next_pending_gate(run: dict[str, Any]) -> dict[str, Any]:
    pending_index = next((index for index, item in enumerate(run["approvalItems"]) if item["status"] == "pending"), -1)
    if pending_index < 0:
        return run

    run = deepcopy(run)
    current = run["approvalItems"][pending_index]
    current["status"] = "rejected"
    run["status"] = "blocked"
    run["updatedAt"] = now_iso()
    run["traceItems"].append(
        make_trace(
            current["requiredBy"],
            f"{current['label']} rejected",
            "Run is blocked and must return to the owner agent with requested changes.",
            "danger",
        )
    )
    return run


def recheck_preview_gate(run: dict[str, Any]) -> dict[str, Any]:
    run = deepcopy(run)
    preview_gate = next((item for item in run["approvalItems"] if item["gate"] == "preview"), None)
    production_gate = next((item for item in run["approvalItems"] if item["gate"] == "production"), None)
    if preview_gate is None or preview_gate.get("status") != "approved":
        raise ValueError("Preview gate must be approved before recheck.")
    if production_gate is None:
        raise ValueError("Production gate is missing.")

    preview_state = attach_preview_publish_result(run)
    if preview_state == "ready":
        if production_gate["status"] in {"locked", "waived"}:
            production_gate["status"] = "pending"
        run["status"] = "waiting-for-approval"
        run["updatedAt"] = now_iso()
        run["traceItems"].append(
            make_trace(
                "devops",
                "Production gate unlocked",
                "Preview is ready. Production approval can continue.",
                "success",
            )
        )
        return run

    production_gate["status"] = "locked"
    run["status"] = "blocked"
    run["updatedAt"] = now_iso()
    run["traceItems"].append(preview_hold_trace(preview_state))
    return run


def normalize_codex_smoke_result(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("result must be an object")
    if payload.get("schema") != "codex_remote_smoke_v0_1":
        raise ValueError("result.schema must be codex_remote_smoke_v0_1")
    if payload.get("status") not in {"pass", "fail"}:
        raise ValueError("result.status must be pass or fail")

    target = payload.get("target")
    if not isinstance(target, dict):
        raise ValueError("result.target is required")
    for key in ["host", "codex", "workdir"]:
        if not str(target.get(key) or "").strip():
            raise ValueError(f"result.target.{key} is required")

    steps = payload.get("steps")
    if not isinstance(steps, list) or not steps:
        raise ValueError("result.steps must be a non-empty list")
    for step in steps:
        if not isinstance(step, dict):
            raise ValueError("result.steps must contain objects")
        if not str(step.get("name") or "").strip():
            raise ValueError("result.steps[].name is required")
        if not isinstance(step.get("passed"), bool):
            raise ValueError("result.steps[].passed must be boolean")

    failure = payload.get("failure")
    if payload["status"] == "fail":
        if not isinstance(failure, dict) or not str(failure.get("class") or "").strip():
            raise ValueError("result.failure.class is required when status is fail")
    elif failure is not None:
        raise ValueError("result.failure must be null when status is pass")

    result = deepcopy(payload)
    result["target"]["healthOnly"] = bool(result["target"].get("healthOnly"))
    return result


def format_codex_smoke_step(step: dict[str, Any]) -> str:
    status = "PASS" if step.get("passed") else "FAIL"
    duration = int(step.get("durationMs") or 0)
    failure_class = str(step.get("failureClass") or "unknown")
    return f"- {step.get('name')}: {status} ({duration}ms, {failure_class})"


def codex_smoke_summary(result: dict[str, Any]) -> str:
    failure = result.get("failure")
    lines = [
        f"Status: {result['status']}",
        f"Host: {result['target']['host']}",
        f"Codex: {result['target']['codex']}",
        f"Workdir: {result['target']['workdir']}",
        f"Health only: {'yes' if result['target']['healthOnly'] else 'no'}",
        "",
        "Steps:",
        *[format_codex_smoke_step(step) for step in result["steps"]],
    ]
    if failure:
        lines.extend(
            [
                "",
                "Failure:",
                f"- class: {failure.get('class')}",
                f"- message: {failure.get('message')}",
            ]
        )
        if failure.get("hint"):
            lines.append(f"- hint: {failure.get('hint')}")
    return "\n".join(lines)


def create_codex_smoke_result_artifact(result: dict[str, Any]) -> dict[str, Any]:
    failure = result.get("failure")
    return {
        "label": "Codex Bridge Smoke Result",
        "kind": "codex-bridge-result",
        "value": codex_smoke_summary(result),
        "metadata": {
            "status": result["status"],
            "targetHost": result["target"]["host"],
            "codexBinary": result["target"]["codex"],
            "healthOnly": result["target"]["healthOnly"],
            "failureClass": failure.get("class") if failure else None,
        },
    }


def attach_codex_bridge_smoke_result(run: dict[str, Any], payload: Any) -> dict[str, Any]:
    result = normalize_codex_smoke_result(payload)
    run = deepcopy(run)
    passed = result["status"] == "pass"
    replace_or_append_artifacts(run, [create_codex_smoke_result_artifact(result)])
    run["traceItems"].append(
        make_trace(
            "devops",
            "Codex bridge smoke passed" if passed else "Codex bridge smoke failed",
            f"{result['target']['host']} can run Codex and return artifacts."
            if passed
            else f"{result['target']['host']} is blocked: {result.get('failure', {}).get('class', 'unknown')}.",
            "success" if passed else "danger",
        )
    )
    if not passed:
        run["status"] = "blocked"
    run["updatedAt"] = now_iso()
    return run


def create_mission_run(payload: dict[str, Any]) -> dict[str, Any]:
    title = str(payload.get("title", "")).strip()
    organization_id = str(payload.get("organizationId", "")).strip()
    lane_id = str(payload.get("laneId", "")).strip()
    if not organization_id:
        raise ValueError("organizationId is required")
    if not title:
        raise ValueError("title is required")
    if lane_id not in LANES:
        raise ValueError("laneId is invalid")
    description = str(payload.get("description") or "No description yet.").strip() or "No description yet."
    priority = str(payload.get("priority") or "medium").strip() or "medium"
    source = normalize_run_source(payload.get("source"))
    if priority not in {"low", "medium", "high", "urgent"}:
        raise ValueError("priority is invalid")
    return build_base_run(
        title=title,
        description=description,
        lane_id=lane_id,
        priority=priority,
        source=source,
    )


def summarize_readiness_counts(readiness: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "ready": sum(1 for item in readiness if item["status"] == "ready"),
        "dryRun": sum(1 for item in readiness if item["status"] == "dry-run"),
        "blocked": sum(1 for item in readiness if item["status"] == "blocked"),
    }


def get_heartbeat_control_state() -> dict[str, Any]:
    armed = is_enabled(env_value("AGENT_OS_HEARTBEAT_ENABLED"))
    missing = []
    if not armed:
        missing.append("AGENT_OS_HEARTBEAT_ENABLED")
    elif not env_value("CRON_SECRET"):
        missing.append("CRON_SECRET")
    return {
        "armed": armed and not missing,
        "mode": "cron-armed" if armed and not missing else "manual-only",
        "summary": (
            "Heartbeat execution is armed by env. Add the production cron schedule only after reviewed approval."
            if armed and not missing
            else "Heartbeat is disarmed. Operators can run read-only checks, but scheduled writes are off."
        ),
        "requiredEnv": ["AGENT_OS_HEARTBEAT_ENABLED", "CRON_SECRET"],
        "missingEnv": missing,
        "cronSchedule": "*/15 * * * *",
    }


def build_integration_status(enabled: bool, missing_env: list[str]) -> str:
    if not enabled:
        return "dry-run"
    return "blocked" if missing_env else "ready"


def get_mission_control_readiness() -> list[dict[str, Any]]:
    github_repo_missing = env_group_missing("AGENT_OS_GITHUB_REPO|GITHUB_REPOSITORY")
    github_token_missing = env_group_missing("AGENT_OS_GITHUB_TOKEN|GITHUB_TOKEN|GH_TOKEN")
    github_issue_missing = github_repo_missing + github_token_missing
    github_issues_enabled = is_enabled(env_value("AGENT_OS_GITHUB_CREATE_ISSUES"))
    github_pr_enabled = is_enabled(env_value("AGENT_OS_GITHUB_CREATE_PULL_REQUEST"))
    github_bootstrap_enabled = is_enabled(env_value("AGENT_OS_GITHUB_BOOTSTRAP_BRANCH"))
    github_pr_missing = list(github_issue_missing)
    if github_pr_enabled and not github_bootstrap_enabled:
        github_pr_missing.append("AGENT_OS_GITHUB_BOOTSTRAP_BRANCH")

    worker_enabled = is_enabled(env_value("AGENT_OS_WORKER_EXECUTE"))
    preview_enabled = vercel_preview_enabled()
    production_enabled = vercel_production_enabled()
    preview_hook = env_value("AGENT_OS_VERCEL_PREVIEW_DEPLOY_HOOK_URL")
    preview_has_link = has_vercel_project_link()
    preview_missing = [] if (preview_hook or preview_has_link) else ["AGENT_OS_VERCEL_PREVIEW_DEPLOY_HOOK_URL or .vercel/project.json"]
    heartbeat = get_heartbeat_control_state()

    return [
        {
            "id": "db-ledger",
            "label": "Mission Run Store",
            "status": "ready",
            "mode": "file-backed json",
            "summary": "Mission runs, approvals, traces, and artifacts are persisted in the Hermes runtime state file.",
            "requiredEnv": [],
            "missingEnv": [],
        },
        {
            "id": "github-issues",
            "label": "GitHub Issues",
            "status": build_integration_status(github_issues_enabled, github_issue_missing),
            "mode": "live requested" if github_issues_enabled else "dry-run",
            "summary": (
                "Issue payloads can be published after repo and token are configured."
                if github_issues_enabled
                else "Issue payloads are prepared and attached without creating GitHub issues."
            ),
            "requiredEnv": [
                "AGENT_OS_GITHUB_CREATE_ISSUES",
                "AGENT_OS_GITHUB_REPO|GITHUB_REPOSITORY",
                "AGENT_OS_GITHUB_TOKEN|GITHUB_TOKEN|GH_TOKEN",
            ],
            "missingEnv": github_issue_missing if github_issues_enabled else ["AGENT_OS_GITHUB_CREATE_ISSUES"],
        },
        {
            "id": "github-pr",
            "label": "GitHub Pull Request",
            "status": build_integration_status(github_pr_enabled, github_pr_missing),
            "mode": "live requested" if github_pr_enabled else "dry-run",
            "summary": (
                "Draft PR creation can create or reuse the worker branch before opening the PR."
                if github_pr_enabled and github_bootstrap_enabled
                else "PR payloads stay attached to the run until the worker branch path is trusted."
            ),
            "requiredEnv": [
                "AGENT_OS_GITHUB_CREATE_PULL_REQUEST",
                "AGENT_OS_GITHUB_BOOTSTRAP_BRANCH",
                "AGENT_OS_GITHUB_REPO|GITHUB_REPOSITORY",
                "AGENT_OS_GITHUB_TOKEN|GITHUB_TOKEN|GH_TOKEN",
            ],
            "missingEnv": github_pr_missing if github_pr_enabled else ["AGENT_OS_GITHUB_CREATE_PULL_REQUEST"],
        },
        {
            "id": "worker",
            "label": "Issue To PR Worker",
            "status": "ready" if worker_enabled else "dry-run",
            "mode": "execute requested" if worker_enabled else "dry-run",
            "summary": (
                "Worker execution is allowed by env; permission and check artifacts still gate the run."
                if worker_enabled
                else "Worker output is simulated, so no files or branches are modified by Mission Control."
            ),
            "requiredEnv": ["AGENT_OS_WORKER_EXECUTE"],
            "missingEnv": [] if worker_enabled else ["AGENT_OS_WORKER_EXECUTE"],
        },
        {
            "id": "vercel-preview",
            "label": "Vercel Preview",
            "status": build_integration_status(
                preview_enabled,
                preview_missing,
            ),
            "mode": "live requested" if preview_enabled else "dry-run",
            "summary": (
                "Preview can be resolved from the linked Vercel project or triggered by a deploy hook."
                if preview_enabled and (preview_hook or preview_has_link)
                else "Preview deploy hook can be triggered after hook URL is configured."
                if preview_enabled
                else "Preview, smoke, rollback, and monitoring plans are attached without triggering Vercel."
            ),
            "requiredEnv": ["AGENT_OS_VERCEL_PREVIEW_DEPLOY", "AGENT_OS_VERCEL_PREVIEW_DEPLOY_HOOK_URL or .vercel/project.json"],
            "missingEnv": preview_missing if preview_enabled else ["AGENT_OS_VERCEL_PREVIEW_DEPLOY"],
        },
        {
            "id": "production",
            "label": "Production Promote",
            "status": "blocked" if production_enabled else "dry-run",
            "mode": "manual command boundary" if production_enabled else "dry-run",
            "summary": (
                "Production promote intentionally stops at a command payload for human execution."
                if production_enabled
                else "Production deploy stays as release note plus promote payload until preview evidence is trusted."
            ),
            "requiredEnv": ["AGENT_OS_VERCEL_PRODUCTION_PROMOTE"],
            "missingEnv": [] if production_enabled else ["AGENT_OS_VERCEL_PRODUCTION_PROMOTE"],
        },
        {
            "id": "heartbeat",
            "label": "24/7 Heartbeat",
            "status": "ready" if heartbeat["armed"] else "dry-run",
            "mode": "trace-writing armed" if heartbeat["armed"] else "manual-only",
            "summary": (
                "Heartbeat trace writes are armed by env; production cron still requires a reviewed change."
                if heartbeat["armed"]
                else "Operators can run read-only checks, but scheduled trace-writing is disarmed."
            ),
            "requiredEnv": heartbeat["requiredEnv"],
            "missingEnv": heartbeat["missingEnv"],
        },
    ]


def probe_status_from_readiness(status: str) -> str:
    if status == "ready":
        return "pass"
    if status == "blocked":
        return "fail"
    return "warn"


def build_integration_health_report(organization_id: str) -> dict[str, Any]:
    checked_at = now_iso()
    readiness = {item["id"]: item for item in get_mission_control_readiness()}
    state = load_state()
    runs = get_runs_for_org(state, organization_id)
    preview_hook = env_value("AGENT_OS_VERCEL_PREVIEW_DEPLOY_HOOK_URL")
    heartbeat = get_heartbeat_control_state()
    probes = [
        {
            "id": "db-ledger",
            "label": "Mission Run Store",
            "status": "pass",
            "summary": "Mission run store read succeeded.",
            "detail": f"{len(runs)} run rows checked without writing data.",
            "checkedAt": checked_at,
            "latencyMs": 1,
        },
        {
            "id": "github-repo",
            "label": "GitHub Repository",
            "status": probe_status_from_readiness(readiness["github-pr"]["status"]),
            "summary": readiness["github-pr"]["summary"],
            "detail": (
                f"Missing: {', '.join(readiness['github-pr']['missingEnv'])}"
                if readiness["github-pr"]["missingEnv"]
                else "Repo and token env appear configured for draft PR mode."
            ),
            "checkedAt": checked_at,
            "latencyMs": 1,
        },
        {
            "id": "github-pr",
            "label": "Draft PR Mode",
            "status": probe_status_from_readiness(readiness["github-pr"]["status"]),
            "summary": readiness["github-pr"]["summary"],
            "detail": (
                f"Missing: {', '.join(readiness['github-pr']['missingEnv'])}"
                if readiness["github-pr"]["missingEnv"]
                else "A pull-request gate can create or reuse a draft PR when the human approves it."
            ),
            "checkedAt": checked_at,
            "latencyMs": 1,
        },
        {
            "id": "vercel-preview",
            "label": "Vercel Preview",
            "status": (
                "pass"
                if readiness["vercel-preview"]["status"] == "ready" and preview_hook
                else probe_status_from_readiness(readiness["vercel-preview"]["status"])
            ),
            "summary": readiness["vercel-preview"]["summary"],
            "detail": (
                "Preview hook URL is configured but is not a valid URL."
                if preview_hook and not preview_hook.startswith(("https://", "http://"))
                else "The health check does not trigger the deploy hook; preview deploy still requires an approval gate."
            ),
            "checkedAt": checked_at,
            "latencyMs": 1,
        },
        {
            "id": "heartbeat",
            "label": "24/7 Heartbeat",
            "status": "pass" if heartbeat["armed"] else "warn",
            "summary": heartbeat["summary"],
            "detail": (
                f"Cron route is armed for {heartbeat['cronSchedule']}."
                if heartbeat["armed"]
                else "Manual read-only checks are available. Scheduled trace writes still need reviewed enablement."
            ),
            "checkedAt": checked_at,
            "latencyMs": 1,
        },
    ]
    totals = {
        "pass": sum(1 for probe in probes if probe["status"] == "pass"),
        "warn": sum(1 for probe in probes if probe["status"] == "warn"),
        "fail": sum(1 for probe in probes if probe["status"] == "fail"),
    }
    return {"checkedAt": checked_at, "probes": probes, "totals": totals}


def collect_daily_ops_signals(organization_id: str) -> dict[str, Any]:
    state = load_state()
    readiness = get_mission_control_readiness()
    runs = get_runs_for_org(state, organization_id)
    pending = 0
    stale = 0
    for run in runs:
        pending_item = next((item for item in run["approvalItems"] if item["status"] == "pending"), None)
        if pending_item:
            pending += 1
            if minutes_since(run["updatedAt"]) >= DEFAULT_STALE_MINUTES:
                stale += 1

    counts = summarize_readiness_counts(readiness)
    return {
        "checkedAt": now_iso(),
        "milestone": {
            "openRuns": sum(1 for run in runs if run["status"] not in {"completed"}),
            "blockedRuns": sum(1 for run in runs if run["status"] == "blocked"),
            "pendingApprovals": pending,
            "staleRuns": stale,
        },
        "productUsage": {
            "encounters7d": 0,
            "encounters30d": 0,
            "completedEncounters30d": 0,
            "bookings7d": 0,
            "clientInvites30d": 0,
        },
        "funnel": {
            "enabledAutomationRules": 0,
            "sentNotifications7d": 0,
            "failedNotifications7d": 0,
            "pendingReminders": 0,
        },
        "operations": {
            "integrationsReady": counts["ready"],
            "integrationsDryRun": counts["dryRun"],
            "integrationsBlocked": counts["blocked"],
        },
    }


def create_daily_ops_run(organization_id: str) -> dict[str, Any]:
    signals = collect_daily_ops_signals(organization_id)
    ops_brief = "\n".join(
        [
            "# 오늘 점검",
            "",
            f"시간: {signals['checkedAt']}",
            "",
            "## 마일스톤",
            f"- 열림: {signals['milestone']['openRuns']}",
            f"- 승인: {signals['milestone']['pendingApprovals']}",
            f"- 막힘: {signals['milestone']['blockedRuns']}",
            f"- 지연: {signals['milestone']['staleRuns']}",
            "",
            "## 연동",
            f"- 준비: {signals['operations']['integrationsReady']}",
            f"- 초안: {signals['operations']['integrationsDryRun']}",
            f"- 막힘: {signals['operations']['integrationsBlocked']}",
            "",
            "## 다음",
            "- 보고서",
            "- 개선 후보",
            "- 승인",
        ]
    )
    return build_base_run(
        title="오늘 운영 점검",
        description="마일스톤, 사용, 유지보수, 퍼널, 모델, 배포 점검. 보고서, 개선, 승인.",
        lane_id="ops-finance",
        priority="high",
        workflow_ids=["daily-ops", "prd-to-issue", "self-improvement"],
        owner_agents=["orchestrator", "planner", "qa", "devops", "backend", "frontend", "db"],
        approval_gates=["plan", "issue", "pull-request"],
        artifacts=[
            {
                "label": "운영",
                "kind": "ops-brief",
                "value": ops_brief,
                "metadata": {"workflow": "daily-ops", "cadence": "manual-live-read"},
            },
            {
                "label": "규칙",
                "kind": "ops-brief",
                "value": "\n".join(
                    [
                        "승인 범위 안에서만 자동 진행.",
                        "",
                        "- 읽기/보고: 가능",
                        "- 이슈/PR 초안: 승인 후",
                        "- 배포/고객/결제/인증/DB: 승인 필요",
                    ]
                ),
                "metadata": {"approvalBoundary": "human-click-required"},
            },
        ],
        trace_items=[
            make_trace("orchestrator", "운영 점검 시작", "마일스톤, 사용, 유지보수, 퍼널, 모델, 배포.", "neutral"),
            make_trace("planner", "계획 승인 대기", "보고서 먼저, 개선은 승인 후.", "warning"),
            make_trace(
                "devops",
                "연동 점검",
                f"준비 {signals['operations']['integrationsReady']}, 초안 {signals['operations']['integrationsDryRun']}, 막힘 {signals['operations']['integrationsBlocked']}.",
                "success" if signals["operations"]["integrationsBlocked"] == 0 else "warning",
            ),
        ],
    )


def create_heartbeat_cron_enablement_run() -> dict[str, Any]:
    cron_path = "/api/cron/agent-os-heartbeat"
    cron_schedule = "*/15 * * * *"
    branch_name = "codex/agent-os-enable-heartbeat-cron"
    pr_body = "\n".join(
        [
            "## Summary",
            "Enable the Agent OS heartbeat cron through a reviewed Vercel cron configuration change.",
            "",
            "## Scope",
            f"- Add {cron_path} to vercel.json crons with schedule `{cron_schedule}`",
            "- Keep the route guarded by CRON_SECRET",
            "- Keep trace writes gated by AGENT_OS_HEARTBEAT_ENABLED=1",
            "- Verify manual read-only Mission Control checks before production promotion",
            "",
            "## Testing",
            "- [ ] pnpm run typecheck",
            "- [ ] curl with CRON_SECRET only succeeds when AGENT_OS_HEARTBEAT_ENABLED=1",
            "- [ ] curl without CRON_SECRET returns 401 where CRON_SECRET is set",
            "",
            "## Risk Notes",
            "- This PR must not approve or deploy production by itself.",
            "- Vercel cron only runs on production deployments.",
            "- Roll back by removing the cron entry or setting AGENT_OS_HEARTBEAT_ENABLED=0.",
        ]
    )
    return build_base_run(
        title="Enable Agent OS heartbeat cron",
        description="Create a reviewed PR request that arms the 24/7 Mission Control heartbeat without bypassing human approval.",
        lane_id="devops",
        priority="high",
        workflow_ids=["issue-to-pr", "pr-to-deploy"],
        owner_agents=["devops", "qa", "orchestrator"],
        approval_gates=["pull-request", "preview", "production"],
        artifacts=[
            {
                "label": "Cron Enablement Boundary",
                "kind": "summary",
                "value": "\n".join(
                    [
                        f"Route: {cron_path}",
                        f"Schedule: {cron_schedule}",
                        "Required env: CRON_SECRET, AGENT_OS_HEARTBEAT_ENABLED=1",
                        "Current action: request only; no direct production cron mutation.",
                    ]
                ),
                "metadata": {"path": cron_path, "schedule": cron_schedule, "requestedMode": "pr-gated"},
            },
            {
                "label": "Vercel Cron Patch",
                "kind": "summary",
                "value": "\n".join(
                    [
                        "Add this entry to vercel.json only after PR approval:",
                        "",
                        json.dumps({"path": cron_path, "schedule": cron_schedule}, ensure_ascii=False, indent=2),
                    ]
                ),
                "metadata": {"file": "vercel.json", "path": cron_path, "schedule": cron_schedule},
            },
            {
                "label": "Draft PR",
                "kind": "pull-request",
                "value": pr_body,
                "metadata": {
                    "title": "[Agent OS] Enable heartbeat cron",
                    "branchName": branch_name,
                    "baseBranch": github_base_branch(),
                },
            },
        ],
        trace_items=[
            make_trace("orchestrator", "Cron enablement requested", "Mission Control generated a PR-gated request for the Agent OS heartbeat cron.", "warning"),
            make_trace("devops", "Safety boundary locked", "The request does not mutate vercel.json, env vars, deployment state, or trace-writing automation.", "success"),
        ],
    )


def heartbeat_check(write_traces: bool = False) -> dict[str, Any]:
    state = load_state()
    readiness = get_mission_control_readiness()
    counts = summarize_readiness_counts(readiness)
    stale_runs = []
    checked_runs = 0
    pending_approvals = 0
    heartbeat_traces = 0
    changed = False

    for organization_id in list(state.get("runsByOrg", {}).keys()):
        runs = state["runsByOrg"][organization_id]
        for index, run in enumerate(runs):
            if run.get("status") in {"completed", "blocked"}:
                continue
            checked_runs += 1
            pending = next((item for item in run["approvalItems"] if item["status"] == "pending"), None)
            if not pending:
                continue
            pending_approvals += 1
            age_minutes = minutes_since(run["updatedAt"])
            if age_minutes >= DEFAULT_STALE_MINUTES:
                stale_runs.append(
                    {
                        "runId": run["id"],
                        "title": run["title"],
                        "status": run["status"],
                        "pendingGate": pending["gate"],
                        "ageMinutes": age_minutes,
                    }
                )
            if write_traces and age_minutes >= DEFAULT_STALE_MINUTES:
                run["traceItems"].append(
                    make_trace(
                        "orchestrator",
                        "24/7 heartbeat check",
                        f"Pending gate: {pending['label']}. Waiting for {age_minutes} minutes. Integrations: {counts['ready']} ready, {counts['dryRun']} dry-run, {counts['blocked']} blocked.",
                        "warning" if counts["blocked"] > 0 else "success",
                    )
                )
                run["updatedAt"] = now_iso()
                runs[index] = run
                heartbeat_traces += 1
                changed = True

    if changed:
        save_state(state)

    return {
        "mode": "trace-writing" if write_traces else "read-only",
        "checkedRuns": checked_runs,
        "pendingApprovals": pending_approvals,
        "heartbeatTraces": heartbeat_traces,
        "staleRuns": stale_runs,
        "integrations": counts,
    }


def request_json(handler: BaseHTTPRequestHandler) -> dict[str, Any]:
    length = int(handler.headers.get("Content-Length", "0"))
    raw = handler.rfile.read(length) if length > 0 else b"{}"
    return json.loads(raw.decode("utf-8"))


class MissionControlHandler(BaseHTTPRequestHandler):
    server_version = "HermesMissionControl/0.1"

    def _json(self, status_code: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, x-hermes-api-key")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _require_auth(self) -> bool:
        if not API_KEY:
            return True
        header_key = (self.headers.get("x-hermes-api-key") or "").strip()
        bearer = self.headers.get("Authorization", "")
        bearer_key = bearer.replace("Bearer ", "", 1).strip() if bearer.startswith("Bearer ") else ""
        if header_key == API_KEY or bearer_key == API_KEY:
            return True
        self._json(401, err("Unauthorized", "UNAUTHORIZED"))
        return False

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, x-hermes-api-key")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()

    def do_GET(self) -> None:
        if not self._require_auth():
            return

        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        organization_id = (params.get("organizationId") or [""])[0].strip()

        try:
            if parsed.path == "/health":
                return self._json(
                    200,
                    ok(
                        {
                            "time": now_iso(),
                            "apiKeyRequired": bool(API_KEY),
                            "statePath": str(STATE_PATH),
                            "eventLog": str(EVENT_LOG),
                        }
                    ),
                )
            if parsed.path == "/runs":
                if not organization_id:
                    return self._json(400, err("organizationId is required", "VALIDATION_ERROR"))
                limit_value = (params.get("limit") or ["30"])[0]
                limit = max(1, min(100, int(limit_value)))
                state = load_state()
                runs = get_runs_for_org(state, organization_id)[:limit]
                return self._json(200, ok(runs))
            if parsed.path == "/a2a-lite/conversations":
                limit_value = (params.get("limit") or [str(DEFAULT_A2A_LIMIT)])[0]
                limit = max(1, min(100, int(limit_value)))
                runs: list[dict[str, Any]] = []
                if organization_id:
                    state = load_state()
                    runs = get_runs_for_org(state, organization_id)
                return self._json(200, ok(list_a2a_lite_conversations(limit=limit, runs=runs)))
            if parsed.path == "/handoffs":
                if not organization_id:
                    return self._json(400, err("organizationId is required", "VALIDATION_ERROR"))
                limit_value = (params.get("limit") or [str(DEFAULT_HANDOFF_LIMIT)])[0]
                limit = max(1, min(100, int(limit_value)))
                status = (params.get("status") or [""])[0].strip() or None
                return self._json(200, ok(list_handoff_items(organization_id, limit=limit, status=status)))
            if parsed.path == "/readiness":
                return self._json(200, ok(get_mission_control_readiness()))
            if parsed.path == "/heartbeat/control":
                return self._json(200, ok(get_heartbeat_control_state()))
            if parsed.path == "/snapshot":
                if not organization_id:
                    return self._json(400, err("organizationId is required", "VALIDATION_ERROR"))
                state = load_state()
                runs = get_runs_for_org(state, organization_id)[:30]
                snapshot = {
                    "runs": runs,
                    "a2aLiteConversations": list_a2a_lite_conversations(runs=runs),
                    "handoffs": list_handoff_items(organization_id),
                    "readiness": get_mission_control_readiness(),
                    "heartbeatControl": get_heartbeat_control_state(),
                }
                return self._json(200, ok(snapshot))
            return self._json(404, err("Not found", "NOT_FOUND"))
        except ValueError as error:
            return self._json(400, err(str(error), "VALIDATION_ERROR"))
        except Exception as error:
            return self._json(500, err(str(error), "INTERNAL_ERROR"))

    def do_POST(self) -> None:
        if not self._require_auth():
            return

        parsed = urlparse(self.path)
        try:
            data = request_json(self)
        except Exception:
            return self._json(400, err("Invalid JSON payload", "VALIDATION_ERROR"))

        try:
            if parsed.path == "/runs":
                run = create_mission_run(data)
                organization_id = str(data.get("organizationId", "")).strip()
                with STATE_LOCK:
                    state = load_state()
                    runs = get_runs_for_org(state, organization_id)
                    runs.append(run)
                    set_runs_for_org(state, organization_id, runs)
                    save_state(state)
                run_source = run.get("source") or {}
                log_event(
                    "run.created",
                    {
                        "organizationId": organization_id,
                        "runId": run["id"],
                        "laneId": run["laneId"],
                        "streamId": run_source.get("streamId"),
                        "channelId": run_source.get("channelId"),
                        "threadId": run_source.get("threadId"),
                    },
                )
                return self._json(200, ok(run))

            if parsed.path == "/handoff/notify":
                event = deepcopy(data)
                event["receivedAt"] = now_iso()
                append_jsonl(HANDOFF_NOTIFY_LOG, event)
                log_event(
                    "continuity-handoff.received",
                    {
                        "handoffId": event.get("handoffId"),
                        "source": event.get("source"),
                        "goal": event.get("goal"),
                    },
                )
                return self._json(
                    200,
                    ok(
                        {
                            "received": True,
                            "handoffId": event.get("handoffId"),
                            "logPath": str(HANDOFF_NOTIFY_LOG),
                        }
                    ),
                )

            if parsed.path == "/handoffs":
                organization_id, item = create_handoff_item(data)
                with STATE_LOCK:
                    state = load_handoff_inbox_state()
                    rows = state.setdefault("handoffsByOrg", {}).setdefault(organization_id, [])
                    if not isinstance(rows, list):
                        rows = []
                        state["handoffsByOrg"][organization_id] = rows
                    rows.append(item)
                    rows.sort(key=lambda row: str(row.get("updatedAt") or row.get("createdAt") or ""), reverse=True)
                    save_handoff_inbox_state(state)
                log_event(
                    "handoff.created",
                    {
                        "organizationId": organization_id,
                        "handoffId": item["id"],
                        "status": item["status"],
                        "repo": item.get("repo"),
                    },
                )
                return self._json(200, ok(item))

            if parsed.path.startswith("/handoffs/") and parsed.path.endswith("/status"):
                handoff_id = parsed.path.split("/")[2]
                try:
                    organization_id, item = update_handoff_status(data, handoff_id)
                except KeyError:
                    return self._json(404, err("Handoff not found", "NOT_FOUND"))
                log_event(
                    "handoff.status_updated",
                    {
                        "organizationId": organization_id,
                        "handoffId": item["id"],
                        "status": item["status"],
                    },
                )
                return self._json(200, ok(item))

            if parsed.path.startswith("/runs/") and parsed.path.endswith("/approve"):
                run_id = parsed.path.split("/")[2]
                organization_id = str(data.get("organizationId", "")).strip()
                if not organization_id:
                    return self._json(400, err("organizationId is required", "VALIDATION_ERROR"))
                with STATE_LOCK:
                    state = load_state()
                    index, current = find_run(state, organization_id, run_id)
                    if current is None:
                        return self._json(404, err("Mission run not found", "NOT_FOUND"))
                    updated = approve_next_pending_gate(current)
                    state["runsByOrg"][organization_id][index] = updated
                    save_state(state)
                log_event("run.approved", {"organizationId": organization_id, "runId": run_id})
                return self._json(200, ok(updated))

            if parsed.path.startswith("/runs/") and parsed.path.endswith("/reject"):
                run_id = parsed.path.split("/")[2]
                organization_id = str(data.get("organizationId", "")).strip()
                if not organization_id:
                    return self._json(400, err("organizationId is required", "VALIDATION_ERROR"))
                with STATE_LOCK:
                    state = load_state()
                    index, current = find_run(state, organization_id, run_id)
                    if current is None:
                        return self._json(404, err("Mission run not found", "NOT_FOUND"))
                    updated = reject_next_pending_gate(current)
                    state["runsByOrg"][organization_id][index] = updated
                    save_state(state)
                log_event("run.rejected", {"organizationId": organization_id, "runId": run_id})
                return self._json(200, ok(updated))

            if parsed.path.startswith("/runs/") and parsed.path.endswith("/recheck-preview"):
                run_id = parsed.path.split("/")[2]
                organization_id = str(data.get("organizationId", "")).strip()
                if not organization_id:
                    return self._json(400, err("organizationId is required", "VALIDATION_ERROR"))
                with STATE_LOCK:
                    state = load_state()
                    index, current = find_run(state, organization_id, run_id)
                    if current is None:
                        return self._json(404, err("Mission run not found", "NOT_FOUND"))
                    updated = recheck_preview_gate(current)
                    state["runsByOrg"][organization_id][index] = updated
                    save_state(state)
                log_event("run.preview-rechecked", {"organizationId": organization_id, "runId": run_id})
                return self._json(200, ok(updated))

            if parsed.path.startswith("/runs/") and parsed.path.endswith("/codex-bridge/smoke-result"):
                run_id = parsed.path.split("/")[2]
                organization_id = str(data.get("organizationId", "")).strip()
                if not organization_id:
                    return self._json(400, err("organizationId is required", "VALIDATION_ERROR"))
                result = data.get("result") if "result" in data else data
                with STATE_LOCK:
                    state = load_state()
                    index, current = find_run(state, organization_id, run_id)
                    if current is None:
                        return self._json(404, err("Mission run not found", "NOT_FOUND"))
                    updated = attach_codex_bridge_smoke_result(current, result)
                    state["runsByOrg"][organization_id][index] = updated
                    save_state(state)
                log_event(
                    "run.codex-bridge-smoke-attached",
                    {
                        "organizationId": organization_id,
                        "runId": run_id,
                        "status": result.get("status") if isinstance(result, dict) else None,
                    },
                )
                return self._json(200, ok(updated))

            if parsed.path == "/daily-ops":
                organization_id = str(data.get("organizationId", "")).strip()
                if not organization_id:
                    return self._json(400, err("organizationId is required", "VALIDATION_ERROR"))
                run = create_daily_ops_run(organization_id)
                with STATE_LOCK:
                    state = load_state()
                    runs = get_runs_for_org(state, organization_id)
                    runs.append(run)
                    set_runs_for_org(state, organization_id, runs)
                    save_state(state)
                log_event("daily-ops.created", {"organizationId": organization_id, "runId": run["id"]})
                return self._json(200, ok(run))

            if parsed.path == "/heartbeat/check":
                write_traces = bool(data.get("writeTraces")) and get_heartbeat_control_state()["armed"]
                result = heartbeat_check(write_traces=write_traces)
                log_event("heartbeat.checked", {"writeTraces": write_traces, "checkedRuns": result["checkedRuns"]})
                return self._json(200, ok(result))

            if parsed.path == "/readiness/check":
                organization_id = str(data.get("organizationId", "")).strip()
                if not organization_id:
                    return self._json(400, err("organizationId is required", "VALIDATION_ERROR"))
                report = build_integration_health_report(organization_id)
                return self._json(200, ok(report))

            if parsed.path == "/heartbeat/cron-request":
                organization_id = str(data.get("organizationId", "")).strip()
                if not organization_id:
                    return self._json(400, err("organizationId is required", "VALIDATION_ERROR"))
                run = create_heartbeat_cron_enablement_run()
                with STATE_LOCK:
                    state = load_state()
                    runs = get_runs_for_org(state, organization_id)
                    runs.append(run)
                    set_runs_for_org(state, organization_id, runs)
                    save_state(state)
                log_event("heartbeat.cron-requested", {"organizationId": organization_id, "runId": run["id"]})
                return self._json(200, ok(run))

            return self._json(404, err("Not found", "NOT_FOUND"))
        except ValueError as error:
            return self._json(400, err(str(error), "VALIDATION_ERROR"))
        except Exception as error:
            return self._json(500, err(str(error), "INTERNAL_ERROR"))


def serve() -> None:
    ensure_parent(STATE_PATH)
    ensure_parent(EVENT_LOG)
    ensure_parent(HANDOFF_NOTIFY_LOG)
    server = ThreadingHTTPServer((HOST, PORT), MissionControlHandler)
    print(f"[mission-control-api] listening on http://{HOST}:{PORT}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[mission-control-api] stopping", flush=True)
    finally:
        server.server_close()


if __name__ == "__main__":
    serve()
