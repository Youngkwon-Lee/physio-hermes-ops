#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

import ingest_discord_meeting_to_mission_control as ingest


DEFAULT_THREAD_ID = "1515296585410416931"
DEFAULT_THREAD_NAME = "맥북코덱스소통채널"
DEFAULT_CHANNEL_NAME = "second_memory"


def first_env(*names: str) -> str | None:
    for name in names:
        value = os.getenv(name, "").strip()
        if value:
            return value
    return None


def load_messages(path: str | None, *, thread_id: str, limit: int, discord_token: str | None) -> list[dict[str, Any]]:
    if path:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            payload = payload.get("messages") or payload.get("items") or []
        if not isinstance(payload, list):
            raise ValueError("messages JSON must be a list or an object with messages/items")
        return [row for row in payload if isinstance(row, dict)]

    if not discord_token:
        raise ValueError("missing Discord bot token; set HERMES_DISCORD_BOT_TOKEN or pass --messages-json for fixture smoke")

    query = urllib.parse.urlencode({"limit": max(1, min(limit, 100))})
    request = urllib.request.Request(
        f"https://discord.com/api/v10/channels/{thread_id}/messages?{query}",
        headers={
            "Authorization": f"Bot {discord_token}",
            "User-Agent": "physio-hermes-ops/0.1",
            "Accept": "application/json",
        },
        method="GET",
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, list):
        raise ValueError("Discord messages response was not a list")
    return [row for row in payload if isinstance(row, dict)]


def message_identity(message: dict[str, Any]) -> dict[str, Any]:
    author = message.get("author") if isinstance(message.get("author"), dict) else {}
    return {
        "messageId": str(message.get("id") or "").strip() or None,
        "createdAt": str(message.get("timestamp") or "").strip() or None,
        "authorId": str(author.get("id") or "").strip() or None,
        "authorName": str(author.get("global_name") or author.get("username") or "").strip() or None,
    }


def extract_marker_block(text: str) -> str | None:
    match = re.search(
        r"MISSION_CONTROL_INGEST_BEGIN\s*(.*?)\s*MISSION_CONTROL_INGEST_END",
        text,
        flags=re.I | re.S,
    )
    return match.group(1).strip() if match else None


def extract_fenced_block(text: str) -> str | None:
    preferred: list[str] = []
    fallback: list[str] = []
    for match in re.finditer(r"```([^\n`]*)\n(.*?)```", text, flags=re.S):
        info = (match.group(1) or "").strip().lower()
        body = match.group(2).strip()
        if not body:
            continue
        if info in {"mission-control-json", "mission-control", "mission-control-md", "mission-control-markdown"}:
            preferred.append(body)
        elif info in {"json", "md", "markdown", ""}:
            fallback.append(body)
    return (preferred or fallback or [None])[0]


def extract_payload(messages: list[dict[str, Any]], *, message_id: str | None, allow_plain: bool) -> tuple[str, dict[str, Any]]:
    ordered = messages
    if message_id:
        ordered = [row for row in messages if str(row.get("id") or "") == message_id]
        if not ordered:
            raise ValueError(f"message id not found: {message_id}")

    for message in ordered:
        content = str(message.get("content") or "").strip()
        if not content:
            continue
        candidate = extract_marker_block(content) or extract_fenced_block(content)
        if not candidate and allow_plain:
            candidate = content
        if not candidate:
            continue
        try:
            ingest.parse_payload(candidate)
        except Exception:
            continue
        return candidate, message_identity(message)

    raise ValueError("no ingestable Mission Control payload found in Discord messages")


def run_ingest(raw: str, args: argparse.Namespace, source_message: dict[str, Any]) -> dict[str, Any]:
    payload = ingest.parse_payload(raw)
    source_thread = ingest.normalize_source_thread(payload, args)
    tasks_raw = payload.get("tasks") or payload.get("actions") or []
    if not isinstance(tasks_raw, list):
        raise ValueError("tasks must be a list")

    plan_payload = ingest.build_plan_payload(payload, args, source_thread)
    plan_payload["sourceMessage"] = source_message
    preview_tasks = [
        ingest.normalize_task(
            task if isinstance(task, dict) else {"title": str(task)},
            args=args,
            plan_id="<created-plan-id>",
            source_thread=source_thread,
            index=index,
        )
        for index, task in enumerate(tasks_raw, start=1)
    ]

    if args.dry_run:
        return {"ok": True, "dryRun": True, "sourceMessage": source_message, "plan": plan_payload, "tasks": preview_tasks}

    base_url = args.base_url.rstrip("/")
    status, plan_body = ingest.request_json(f"{base_url}/plans", args.token, method="POST", payload=plan_payload)
    if status != 200 or not isinstance(plan_body, dict) or not plan_body.get("ok"):
        return {"ok": False, "stage": "create_plan", "status": status, "response": plan_body}

    plan = plan_body.get("item") or plan_body.get("data") or {}
    plan_id = str(plan.get("id") or "")
    created_tasks = []
    for index, task in enumerate(tasks_raw, start=1):
        task_payload = ingest.normalize_task(
            task if isinstance(task, dict) else {"title": str(task)},
            args=args,
            plan_id=plan_id,
            source_thread=source_thread,
            index=index,
        )
        task_status, task_body = ingest.request_json(f"{base_url}/tasks", args.token, method="POST", payload=task_payload)
        created_tasks.append({"status": task_status, "response": task_body})
        if task_status != 200 or not isinstance(task_body, dict) or not task_body.get("ok"):
            return {"ok": False, "stage": "create_task", "plan": plan, "tasks": created_tasks}

    return {
        "ok": True,
        "sourceMessage": source_message,
        "plan": plan,
        "tasks": [(row["response"].get("item") or row["response"].get("data")) for row in created_tasks],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ingest a bounded Discord thread meeting payload into Mission Control.")
    parser.add_argument("--thread-id", default=DEFAULT_THREAD_ID)
    parser.add_argument("--thread-name", default=DEFAULT_THREAD_NAME)
    parser.add_argument("--channel-name", default=DEFAULT_CHANNEL_NAME)
    parser.add_argument("--message-id", default=None, help="Only inspect one Discord message id.")
    parser.add_argument("--messages-json", default=None, help="Fixture JSON list of Discord messages; skips Discord API.")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--allow-plain", action="store_true", help="Allow a whole message body as the meeting note if no fence/marker exists.")
    parser.add_argument("--discord-token", default=first_env("HERMES_DISCORD_BOT_TOKEN", "DISCORD_BOT_TOKEN"))
    parser.add_argument("--base-url", default=first_env("MISSION_CONTROL_BASE_URL", "HERMES_DESKTOP_MISSION_CONTROL_URL") or "http://100.83.147.56:8792")
    parser.add_argument("--token", default=first_env("MISSION_CONTROL_SHARED_TOKEN", "HERMES_MISSION_CONTROL_API_KEY") or "dev-local-mission-control")
    parser.add_argument("--organization-id", default="org-smoke")
    parser.add_argument("--repo", default="Youngkwon-Lee/physio-hermes-ops")
    parser.add_argument("--default-owner", default="youngkwon")
    parser.add_argument("--default-assignee", default="desktop-hermes")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        messages = load_messages(args.messages_json, thread_id=args.thread_id, limit=args.limit, discord_token=args.discord_token)
        raw, source_message = extract_payload(messages, message_id=args.message_id, allow_plain=args.allow_plain)
        result = run_ingest(raw, args, source_message)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result.get("ok") else 1
    except Exception as error:
        print(json.dumps({"ok": False, "error": f"{type(error).__name__}: {error}"}, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
