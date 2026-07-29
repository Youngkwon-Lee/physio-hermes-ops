#!/usr/bin/env python3
"""Approval-gated dispatch for privacy-safe Open Minis capture routes."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


SCHEMA = "capture-route-state-v1"
QUEUE_SCHEMA = "capture-route-decision-v1"
DESTINATIONS = {"kinelo_ops", "physio_app", "second_brain", "hold", "discard"}
DECISIONS = {"approve", "hold", "reject"}
TERMINAL_STATUSES = {"dispatched", "rejected"}


class CaptureRouteError(RuntimeError):
    pass


class DispatchBlocked(CaptureRouteError):
    pass


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _compact(value: Any, limit: int) -> str:
    text = " ".join(str(value or "").split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _payload_hash(item: dict[str, Any]) -> str:
    safe_payload = {
        key: item.get(key)
        for key in (
            "captureId",
            "sourcePath",
            "sourceSchema",
            "title",
            "summary",
            "sensitivity",
            "proposedDestination",
            "proposedObjectType",
        )
    }
    encoded = json.dumps(safe_payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _write_json_atomic(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
        temp_path = Path(handle.name)
    os.replace(temp_path, path)


def empty_state() -> dict[str, Any]:
    return {"schema": SCHEMA, "updatedAt": now_iso(), "routesByOrg": {}}


def _safe_item(raw: dict[str, Any], timestamp: str) -> dict[str, Any]:
    capture_id = _compact(raw.get("capture_id") or raw.get("captureId"), 80)
    if not capture_id:
        raise CaptureRouteError("capture id is required")
    destination = _compact(raw.get("proposed_destination") or raw.get("proposedDestination"), 40)
    if destination not in DESTINATIONS:
        raise CaptureRouteError(f"unsupported destination for {capture_id}: {destination}")
    sensitivity = _compact(raw.get("sensitivity"), 40) or "unknown"
    restricted = sensitivity.casefold() in {"restricted", "sensitive", "private"}
    title = "민감정보 검토 필요" if restricted else _compact(raw.get("title"), 300)
    summary = "보호된 원본을 사람이 검토해야 합니다." if restricted else _compact(raw.get("summary"), 1200)
    return {
        "captureId": capture_id,
        "sourcePath": _compact(raw.get("source_path") or raw.get("sourcePath"), 800),
        "sourceSchema": _compact(raw.get("source_schema") or raw.get("sourceSchema"), 100),
        "capturedAt": _compact(raw.get("captured_at") or raw.get("capturedAt"), 80),
        "title": title,
        "summary": summary,
        "sensitivity": sensitivity,
        "suggestedRoute": _compact(raw.get("suggested_route") or raw.get("suggestedRoute"), 100),
        "proposedDestination": destination,
        "proposedObjectType": _compact(raw.get("proposed_object_type") or raw.get("proposedObjectType"), 100),
        "confidence": _compact(raw.get("confidence"), 40),
        "reason": _compact(raw.get("reason"), 500),
        "status": "pending",
        "createdAt": timestamp,
        "updatedAt": timestamp,
        "decision": None,
        "decidedAt": None,
        "decidedBy": None,
        "approvedPayloadHash": None,
        "dispatch": None,
    }


class CaptureRouteStore:
    def __init__(self, path: Path):
        self.path = path
        self._lock = RLock()

    def load(self) -> dict[str, Any]:
        with self._lock:
            state = _read_json(self.path, empty_state())
            if not isinstance(state, dict) or state.get("schema") != SCHEMA:
                return empty_state()
            if not isinstance(state.get("routesByOrg"), dict):
                state["routesByOrg"] = {}
            return state

    def save(self, state: dict[str, Any]) -> None:
        with self._lock:
            state["schema"] = SCHEMA
            state["updatedAt"] = now_iso()
            _write_json_atomic(self.path, state)

    def list(self, organization_id: str) -> list[dict[str, Any]]:
        with self._lock:
            rows = self.load().get("routesByOrg", {}).get(organization_id, [])
            if not isinstance(rows, list):
                return []
            return sorted(
                [dict(row) for row in rows if isinstance(row, dict)],
                key=lambda row: str(row.get("updatedAt") or row.get("createdAt") or ""),
                reverse=True,
            )

    def get(self, organization_id: str, capture_id: str) -> dict[str, Any] | None:
        return next((row for row in self.list(organization_id) if row.get("captureId") == capture_id), None)

    def sync(self, organization_id: str, queue: dict[str, Any]) -> dict[str, int]:
        if queue.get("schema") != QUEUE_SCHEMA or queue.get("approval_required") is not True:
            raise CaptureRouteError("approval-required capture route queue is required")
        raw_items = queue.get("items")
        if not isinstance(raw_items, list):
            raise CaptureRouteError("queue items must be a list")

        with self._lock:
            timestamp = now_iso()
            state = self.load()
            rows = state.setdefault("routesByOrg", {}).setdefault(organization_id, [])
            by_id = {str(row.get("captureId")): index for index, row in enumerate(rows) if isinstance(row, dict)}
            created = updated = preserved = 0
            for raw in raw_items:
                if not isinstance(raw, dict):
                    continue
                incoming = _safe_item(raw, timestamp)
                index = by_id.get(incoming["captureId"])
                if index is None:
                    rows.append(incoming)
                    by_id[incoming["captureId"]] = len(rows) - 1
                    created += 1
                    continue
                current = rows[index]
                if current.get("status") != "pending":
                    preserved += 1
                    continue
                incoming["createdAt"] = current.get("createdAt") or timestamp
                rows[index] = incoming
                updated += 1
            self.save(state)
            return {"created": created, "updated": updated, "preserved": preserved, "total": len(rows)}

    def decide(
        self,
        organization_id: str,
        capture_id: str,
        decision: str,
        actor: str,
        destination: str | None = None,
    ) -> dict[str, Any]:
        if decision not in DECISIONS:
            raise CaptureRouteError(f"unsupported decision: {decision}")
        with self._lock:
            state = self.load()
            rows = state.setdefault("routesByOrg", {}).setdefault(organization_id, [])
            index = next((i for i, row in enumerate(rows) if row.get("captureId") == capture_id), -1)
            if index < 0:
                raise CaptureRouteError("capture route not found")
            current = dict(rows[index])
            if current.get("status") in TERMINAL_STATUSES:
                raise CaptureRouteError(f"route is terminal: {current.get('status')}")

            timestamp = now_iso()
            if decision == "approve":
                sensitivity = str(current.get("sensitivity") or "").casefold()
                if sensitivity in {"restricted", "sensitive", "private"}:
                    raise DispatchBlocked("restricted capture cannot be approved")
                selected = destination or current.get("proposedDestination")
                if selected not in {"kinelo_ops", "physio_app", "second_brain"}:
                    raise DispatchBlocked("approved destination must own a durable record")
                current["proposedDestination"] = selected
                current["status"] = "approved"
                current["approvedPayloadHash"] = _payload_hash(current)
            elif decision == "hold":
                current["status"] = "held"
                current["approvedPayloadHash"] = None
            else:
                current["status"] = "rejected"
                current["approvedPayloadHash"] = None
            current.update({"decision": decision, "decidedAt": timestamp, "decidedBy": _compact(actor, 100), "updatedAt": timestamp})
            rows[index] = current
            self.save(state)
            return current

    def record_dispatch(self, organization_id: str, capture_id: str, result: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            state = self.load()
            rows = state.setdefault("routesByOrg", {}).setdefault(organization_id, [])
            index = next((i for i, row in enumerate(rows) if row.get("captureId") == capture_id), -1)
            if index < 0:
                raise CaptureRouteError("capture route not found")
            current = dict(rows[index])
            current["status"] = "dispatched" if result.get("ok") else "dispatch_failed"
            current["dispatch"] = result
            current["updatedAt"] = now_iso()
            rows[index] = current
            self.save(state)
            return current


def request_json(
    url: str,
    *,
    method: str = "GET",
    token: str | None = None,
    payload: dict[str, Any] | None = None,
    extra_headers: dict[str, str] | None = None,
    timeout: int = 15,
) -> tuple[int, dict[str, Any] | str]:
    headers = {"Accept": "application/json", **(extra_headers or {})}
    if token:
        headers["Authorization"] = f"Bearer {token}"
        headers["x-hermes-api-key"] = token
    data = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = Request(url, method=method, headers=headers, data=data)
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8", errors="replace")
            return response.status, json.loads(raw) if raw else {}
    except HTTPError as error:
        raw = error.read().decode("utf-8", errors="replace")
        try:
            return error.code, json.loads(raw) if raw else {}
        except ValueError:
            return error.code, raw
    except (URLError, OSError) as error:
        return 0, f"{type(error).__name__}: {error}"


def _mission_task_payload(item: dict[str, Any], organization_id: str) -> dict[str, Any]:
    destination = item["proposedDestination"]
    repo = "/home/yk/physio_app" if destination == "physio_app" else "/home/yk/brain-linux"
    expected = (
        "Create a privacy-safe product operations evidence/backlog item and return its owning-system ID and URL."
        if destination == "physio_app"
        else "Review the candidate and create the smallest approved Second Brain promotion patch; return the canonical path."
    )
    return {
        "id": f"capture-{destination}-{item['captureId'].lower()}",
        "organizationId": organization_id,
        "status": "ready",
        "title": f"[{item['captureId']}] {item['title']}",
        "context": _compact(f"{item.get('summary') or ''} Source: {item.get('sourcePath') or ''}", 1200),
        "expectedOutput": expected,
        "repo": repo,
        "priority": 40,
        "assignee": {"agent": "macbook-codex", "surface": "codex-app", "host": "macbook"},
        "tags": ["capture-route", destination, item["captureId"]],
    }


def _kinelo_payload(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": f"[{item['captureId']}] {item['title']}",
        "description": _compact(f"{item.get('summary') or ''} Source: {item.get('sourcePath') or ''}", 1200),
        "status": "todo",
        "priority": "medium",
        "source_provider": "api",
        "source_external_id": item["captureId"],
        "agent_lane": "hermes",
    }


def dispatch_route(
    store: CaptureRouteStore,
    organization_id: str,
    capture_id: str,
    *,
    execute: bool,
    http_request: Callable[..., tuple[int, dict[str, Any] | str]] = request_json,
) -> dict[str, Any]:
    item = store.get(organization_id, capture_id)
    if item is None:
        raise CaptureRouteError("capture route not found")
    if item.get("status") == "dispatched" and isinstance(item.get("dispatch"), dict):
        return item["dispatch"]
    if item.get("status") not in {"approved", "dispatch_failed"}:
        raise DispatchBlocked("route must be explicitly approved before dispatch")
    if item.get("approvedPayloadHash") != _payload_hash(item):
        raise DispatchBlocked("approved payload changed after approval")

    previous_dispatch = item.get("dispatch") if isinstance(item.get("dispatch"), dict) else {}
    try:
        attempt = max(0, int(previous_dispatch.get("attempt") or 0)) + 1
    except (TypeError, ValueError):
        attempt = 1

    destination = item["proposedDestination"]
    if destination == "kinelo_ops":
        base_url = os.getenv("KINELO_OPS_BASE_URL", "").rstrip("/")
        intake_url = os.getenv("KINELO_OPS_INTAKE_URL", "").strip()
        secret = os.getenv("KINELO_OPS_INTAKE_SECRET", "").strip()
        url = intake_url or (f"{base_url}/api/ops-intake" if base_url else "")
        payload = _kinelo_payload(item)
        headers = {"x-kinelo-intake-secret": secret} if secret else {}
        missing = [
            name
            for name, value in (
                ("KINELO_OPS_INTAKE_URL or KINELO_OPS_BASE_URL", url),
                ("KINELO_OPS_INTAKE_SECRET", secret),
            )
            if not value
        ]
    else:
        base_url = os.getenv("MISSION_CONTROL_BASE_URL", "http://127.0.0.1:8792").rstrip("/")
        token = os.getenv("MISSION_CONTROL_SHARED_TOKEN", "").strip() or None
        url = f"{base_url}/tasks"
        payload = _mission_task_payload(item, organization_id)
        headers = {}
        missing = []

    preview = {"ok": True, "dryRun": True, "captureId": capture_id, "destination": destination, "url": url, "payload": payload}
    if not execute:
        return preview
    if missing:
        raise DispatchBlocked("missing dispatch configuration: " + ", ".join(missing))

    readback: dict[str, Any]
    if destination == "kinelo_ops":
        status, body = http_request(url, method="POST", payload=payload, extra_headers=headers)
        response_id = body.get("taskId") if isinstance(body, dict) else None
        readback = {
            "ok": 200 <= status < 300 and bool(response_id),
            "verifiedBy": "write_response",
            "recordId": response_id,
        }
    else:
        task_id = payload["id"]
        query = urlencode({"organizationId": organization_id, "limit": 100})
        read_status, read_body = http_request(f"{base_url}/tasks?{query}", token=token)
        existing = []
        if read_status == 200 and isinstance(read_body, dict):
            existing = read_body.get("items") or read_body.get("data") or []
        if any(isinstance(row, dict) and row.get("id") == task_id for row in existing):
            status, body = 200, {"ok": True, "deduped": True, "taskId": task_id}
        else:
            status, body = http_request(url, method="POST", token=token, payload=payload)
        read_status, read_body = http_request(f"{base_url}/tasks?{query}", token=token)
        read_items = []
        if read_status == 200 and isinstance(read_body, dict):
            read_items = read_body.get("items") or read_body.get("data") or []
        read_item = next(
            (row for row in read_items if isinstance(row, dict) and row.get("id") == task_id),
            None,
        )
        readback = {
            "ok": read_status == 200 and read_item is not None,
            "verifiedBy": "mission_control_tasks_get",
            "statusCode": read_status,
            "recordId": task_id if read_item is not None else None,
        }
    result = {
        "ok": 200 <= status < 300 and readback["ok"],
        "dryRun": False,
        "captureId": capture_id,
        "destination": destination,
        "attempt": attempt,
        "statusCode": status,
        "response": body,
        "readback": readback,
        "dispatchedAt": now_iso(),
    }
    return store.record_dispatch(organization_id, capture_id, result).get("dispatch") or result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, default=Path(os.getenv("CAPTURE_ROUTE_STATE_PATH", Path.home() / ".local/state/physio-hermes-ops/mission_control/capture_routes.json")))
    parser.add_argument("--organization-id", default=os.getenv("MISSION_CONTROL_ORGANIZATION_ID", "org-smoke"))
    subparsers = parser.add_subparsers(dest="command", required=True)
    sync = subparsers.add_parser("sync")
    sync.add_argument("--queue", type=Path, required=True)
    subparsers.add_parser("list")
    decide = subparsers.add_parser("decide")
    decide.add_argument("--capture-id", required=True)
    decide.add_argument("--decision", choices=sorted(DECISIONS), required=True)
    decide.add_argument("--actor", required=True)
    decide.add_argument("--destination", choices=sorted(DESTINATIONS))
    dispatch = subparsers.add_parser("dispatch")
    dispatch.add_argument("--capture-id", required=True)
    dispatch.add_argument("--execute", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    store = CaptureRouteStore(args.state)
    try:
        if args.command == "sync":
            output = store.sync(args.organization_id, _read_json(args.queue, {}))
        elif args.command == "list":
            output = {"items": store.list(args.organization_id)}
        elif args.command == "decide":
            output = store.decide(args.organization_id, args.capture_id, args.decision, args.actor, args.destination)
        else:
            output = dispatch_route(store, args.organization_id, args.capture_id, execute=args.execute)
    except CaptureRouteError as error:
        print(json.dumps({"ok": False, "error": str(error)}, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps({"ok": True, "data": output}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
