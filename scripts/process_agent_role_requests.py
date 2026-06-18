#!/usr/bin/env python3
"""Process Mission Control agent role request handoffs.

This is intentionally conservative: it does not create Discord applications or
tokens. It converts an operator request into a tracked Hermes task and writes a
bounded result back to the handoff.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


DEFAULT_BASE_URL = "http://100.83.147.56:8792"
DEFAULT_LIMIT = 50


def compact(value: Any, limit: int = 320) -> str:
    text = " ".join(str(value or "").split())
    return text[:limit]


def request_json(
    base_url: str,
    path: str,
    token: str | None,
    *,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    url = base_url.rstrip("/") + path
    body = None
    headers = {"Accept": "application/json"}
    if token:
        headers["x-hermes-api-key"] = token
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=12) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method} {url} failed: {error.code} {detail}") from error


def get_data(response: dict[str, Any]) -> Any:
    if response.get("success") is False or response.get("ok") is False:
        raise RuntimeError(str(response.get("error") or response))
    if "data" in response:
        return response["data"]
    if "items" in response:
        return response["items"]
    return response.get("item")


def handoff_thread_label(item: dict[str, Any]) -> str:
    thread = item.get("sourceThread") if isinstance(item.get("sourceThread"), dict) else {}
    channel_name = compact(thread.get("channelName"), 80)
    thread_name = compact(thread.get("threadName"), 80)
    if channel_name and thread_name:
        return f"{channel_name} > {thread_name}"
    return thread_name or channel_name or "-"


def agent_name_from_goal(goal: str) -> str:
    prefix = "에이전트 추가:"
    if goal.startswith(prefix):
        return goal[len(prefix):].strip() or "새 에이전트"
    return goal.strip() or "새 에이전트"


def build_result(item: dict[str, Any], task: dict[str, Any] | None, *, duplicate: bool) -> str:
    goal = compact(item.get("goal"), 180)
    context = compact(item.get("context"), 900)
    task_id = task.get("id") if task else None
    lines = [
        "Hermes가 에이전트 추가 요청을 접수했습니다.",
        f"요청: {goal}",
        f"쓰레드: {handoff_thread_label(item)}",
        f"작업: {'기존 task 재사용' if duplicate else 'task 생성'}{f' ({task_id})' if task_id else ''}",
        "",
        "실제 Discord 봇 생성은 Discord Developer Portal 권한과 토큰 발급이 필요합니다.",
        "현재 자동화 범위는 요청 접수, 작업화, 권한/일정/기능 검토, 다음 작업 보고입니다.",
        "",
        "다음:",
        "1. 필요한 봇/에이전트 역할 확정",
        "2. Discord 채널/쓰레드 권한 확인",
        "3. Hermes agent profile/skill/routing 설정",
        "4. Mission Control에서 상태 확인",
    ]
    if context:
        lines.extend(["", "요청 내용:", context])
    return "\n".join(lines)


def list_agent_role_handoffs(base_url: str, token: str | None, organization_id: str, limit: int) -> list[dict[str, Any]]:
    query = urllib.parse.urlencode({
        "organizationId": organization_id,
        "limit": str(limit),
        "status": "needs_reply",
    })
    response = request_json(base_url, f"/handoffs?{query}", token)
    items = get_data(response)
    if not isinstance(items, list):
        return []
    return [
        item for item in items
        if isinstance(item, dict) and item.get("kind") == "agent_role_request"
    ]


def list_tasks(base_url: str, token: str | None, organization_id: str, limit: int) -> list[dict[str, Any]]:
    query = urllib.parse.urlencode({
        "organizationId": organization_id,
        "limit": str(limit),
    })
    response = request_json(base_url, f"/tasks?{query}", token)
    items = get_data(response)
    return items if isinstance(items, list) else []


def create_task(base_url: str, token: str | None, organization_id: str, item: dict[str, Any]) -> dict[str, Any]:
    name = agent_name_from_goal(str(item.get("goal") or ""))
    payload = {
        "organizationId": organization_id,
        "title": f"에이전트 설정 검토: {name}",
        "status": "ready",
        "context": item.get("context") or "",
        "expectedOutput": item.get("expectedOutput") or "가능 여부와 다음 작업 보고",
        "assignee": {
            "agent": "desktop-hermes",
            "surface": "hermes",
            "host": "desktop",
        },
        "repo": item.get("repo") or "Youngkwon-Lee/physio-hermes-ops",
        "sourceThread": item.get("sourceThread") or {},
        "priority": 40,
        "linkedHandoffId": item.get("id"),
        "tags": ["agent-request", "discord-thread", "mission-control"],
    }
    response = request_json(base_url, "/tasks", token, method="POST", payload=payload)
    task = get_data(response)
    if not isinstance(task, dict):
        raise RuntimeError(f"unexpected task response: {response}")
    return task


def update_handoff_status(
    base_url: str,
    token: str | None,
    organization_id: str,
    handoff_id: str,
    status: str,
    result: str,
) -> dict[str, Any]:
    payload = {
        "organizationId": organization_id,
        "status": status,
        "result": result,
    }
    response = request_json(
        base_url,
        f"/handoffs/{urllib.parse.quote(handoff_id)}/status",
        token,
        method="POST",
        payload=payload,
    )
    updated = get_data(response)
    if not isinstance(updated, dict):
        raise RuntimeError(f"unexpected handoff response: {response}")
    return updated


def process_requests(args: argparse.Namespace) -> dict[str, Any]:
    token = args.token or None
    handoffs = list_agent_role_handoffs(args.base_url, token, args.organization_id, args.limit)
    tasks = list_tasks(args.base_url, token, args.organization_id, max(args.limit, 100))
    tasks_by_handoff = {
        str(task.get("linkedHandoffId")): task
        for task in tasks
        if isinstance(task, dict) and task.get("linkedHandoffId")
    }

    processed: list[dict[str, Any]] = []
    for item in handoffs:
        handoff_id = str(item.get("id") or "").strip()
        if not handoff_id:
            continue

        existing_task = tasks_by_handoff.get(handoff_id)
        duplicate = existing_task is not None
        task = existing_task

        if not args.dry_run and task is None:
            task = create_task(args.base_url, token, args.organization_id, item)

        result = build_result(item, task, duplicate=duplicate)
        updated = None
        if not args.dry_run:
            updated = update_handoff_status(
                args.base_url,
                token,
                args.organization_id,
                handoff_id,
                args.close_status,
                result,
            )

        processed.append({
            "handoffId": handoff_id,
            "goal": item.get("goal"),
            "taskId": task.get("id") if isinstance(task, dict) else None,
            "duplicateTask": duplicate,
            "status": updated.get("status") if isinstance(updated, dict) else args.close_status,
        })

    return {
        "ok": True,
        "dryRun": args.dry_run,
        "organizationId": args.organization_id,
        "processedCount": len(processed),
        "processed": processed,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Convert Mission Control agent-role handoffs into Hermes tasks.")
    parser.add_argument(
        "--base-url",
        default=os.getenv("MISSION_CONTROL_BASE_URL") or os.getenv("HERMES_MISSION_CONTROL_BASE_URL") or DEFAULT_BASE_URL,
        help="Mission Control API base URL.",
    )
    parser.add_argument(
        "--token",
        default=os.getenv("MISSION_CONTROL_SHARED_TOKEN") or os.getenv("HERMES_MISSION_CONTROL_API_KEY"),
        help="Mission Control shared token.",
    )
    parser.add_argument(
        "--organization-id",
        default=os.getenv("MISSION_CONTROL_ORGANIZATION_ID"),
        required=not bool(os.getenv("MISSION_CONTROL_ORGANIZATION_ID")),
        help="Organization id to process.",
    )
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    parser.add_argument("--close-status", choices=["done", "in_progress", "blocked"], default="done")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    try:
        result = process_requests(parse_args())
    except Exception as error:
        print(json.dumps({"ok": False, "error": str(error)}, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
