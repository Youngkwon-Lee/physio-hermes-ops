#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from urllib.error import HTTPError, URLError
from pathlib import Path
from typing import Any

import ingest_discord_meeting_to_mission_control as ingest


DEFAULT_THREAD_ID = "1515296585410416931"
DEFAULT_THREAD_NAME = "맥북코덱스소통채널"
DEFAULT_CHANNEL_NAME = "second_memory"
DEFAULT_STATE_FILE = Path.home() / ".local" / "state" / "physio-hermes-ops" / "mission_control" / "discord_thread_ingest_state.json"


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


def load_state(path: str | None) -> dict[str, Any]:
    if not path:
        return {"processedMessageIds": []}
    state_path = Path(path).expanduser()
    if not state_path.exists():
        return {"processedMessageIds": []}
    raw = state_path.read_text(encoding="utf-8").strip()
    if not raw:
        return {"processedMessageIds": []}
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        return {"processedMessageIds": []}
    if not isinstance(payload.get("processedMessageIds"), list):
        payload["processedMessageIds"] = []
    return payload


def save_state(path: str | None, state: dict[str, Any]) -> None:
    if not path:
        return
    state_path = Path(path).expanduser()
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def mark_processed(state: dict[str, Any], source_message: dict[str, Any], result: dict[str, Any]) -> None:
    message_id = str(source_message.get("messageId") or "").strip()
    if not message_id:
        return
    processed = [str(value) for value in state.get("processedMessageIds", []) if str(value).strip()]
    if message_id not in processed:
        processed.append(message_id)
    state["processedMessageIds"] = processed[-500:]
    state["lastProcessedMessageId"] = message_id
    state["lastResult"] = {
        "ok": bool(result.get("ok")),
        "planId": (result.get("plan") or {}).get("id") if isinstance(result.get("plan"), dict) else None,
        "taskIds": [
            task.get("id")
            for task in result.get("tasks", [])
            if isinstance(task, dict) and task.get("id")
        ],
        "kineloOpsMirrorCount": len(
            [
                row
                for row in result.get("kineloOpsMirrors", [])
                if isinstance(row, dict) and row.get("ok")
            ]
        ),
    }


def discord_source_url(source_thread: dict[str, Any], source_message: dict[str, Any], guild_id: str | None) -> str | None:
    explicit_url = str(source_thread.get("url") or "").strip()
    if explicit_url:
        return explicit_url

    thread_id = str(source_thread.get("threadId") or "").strip()
    message_id = str(source_message.get("messageId") or "").strip()
    if not thread_id:
        return None

    server_id = (guild_id or "@me").strip() or "@me"
    if message_id:
        return f"https://discord.com/channels/{server_id}/{thread_id}/{message_id}"
    return f"https://discord.com/channels/{server_id}/{thread_id}"


def kinelo_priority(value: Any) -> str:
    try:
        priority = int(value)
    except (TypeError, ValueError):
        return "medium"
    if priority <= 10:
        return "urgent"
    if priority <= 30:
        return "high"
    if priority >= 80:
        return "low"
    return "medium"


def mirror_task_to_kinelo_ops(
    task_payload: dict[str, Any],
    *,
    args: argparse.Namespace,
    source_thread: dict[str, Any],
    source_message: dict[str, Any],
    index: int,
) -> dict[str, Any]:
    if not args.kinelo_ops_intake_url or not args.kinelo_ops_intake_secret:
        return {"ok": True, "skipped": True, "reason": "kinelo ops intake is not configured"}

    source_url = discord_source_url(source_thread, source_message, args.discord_guild_id)
    external_parts = [
        "discord-thread",
        str(source_thread.get("threadId") or args.thread_id or "").strip(),
        str(source_message.get("messageId") or "").strip(),
        str(index),
    ]
    source_external_id = ":".join([part for part in external_parts if part])
    context = str(task_payload.get("context") or "").strip()
    expected_output = str(task_payload.get("expectedOutput") or "").strip()
    description = "\n\n".join([part for part in [context, f"Expected output: {expected_output}" if expected_output else ""] if part])
    assignee = task_payload.get("assignee") if isinstance(task_payload.get("assignee"), dict) else {}

    payload = {
        "title": task_payload.get("title") or f"Discord task {index}",
        "description": description or None,
        "priority": kinelo_priority(task_payload.get("priority")),
        "owner": assignee.get("agent") or args.default_assignee,
        "source_provider": "discord",
        "source_url": source_url,
        "source_external_id": source_external_id or None,
    }
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        args.kinelo_ops_intake_url,
        data=data,
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {args.kinelo_ops_intake_secret}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            body = response.read().decode("utf-8", errors="replace")
            parsed = json.loads(body) if body else {}
            return {
                "ok": 200 <= response.status < 300,
                "status": response.status,
                "taskId": parsed.get("taskId") if isinstance(parsed, dict) else None,
                "deduped": bool(parsed.get("deduped")) if isinstance(parsed, dict) else False,
                "sourceExternalId": source_external_id,
            }
    except HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        return {"ok": False, "status": error.code, "error": body[:500], "sourceExternalId": source_external_id}
    except (URLError, TimeoutError) as error:
        return {"ok": False, "status": 0, "error": str(error), "sourceExternalId": source_external_id}


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


def extract_payload(
    messages: list[dict[str, Any]],
    *,
    message_id: str | None,
    allow_plain: bool,
    processed_message_ids: set[str] | None = None,
) -> tuple[str, dict[str, Any]]:
    ordered = messages
    if message_id:
        ordered = [row for row in messages if str(row.get("id") or "") == message_id]
        if not ordered:
            raise ValueError(f"message id not found: {message_id}")
    processed_message_ids = processed_message_ids or set()

    for message in ordered:
        if str(message.get("id") or "") in processed_message_ids:
            continue
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
    kinelo_ops_mirrors = []
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
            return {"ok": False, "stage": "create_task", "plan": plan, "tasks": created_tasks, "kineloOpsMirrors": kinelo_ops_mirrors}
        kinelo_ops_mirrors.append(
            mirror_task_to_kinelo_ops(
                task_payload,
                args=args,
                source_thread=source_thread,
                source_message=source_message,
                index=index,
            )
        )

    return {
        "ok": True,
        "sourceMessage": source_message,
        "plan": plan,
        "tasks": [(row["response"].get("item") or row["response"].get("data")) for row in created_tasks],
        "kineloOpsMirrors": kinelo_ops_mirrors,
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
    parser.add_argument("--state-file", default=str(DEFAULT_STATE_FILE), help="Processed message state path. Use empty string with --no-state.")
    parser.add_argument("--no-state", action="store_true", help="Disable duplicate prevention state.")
    parser.add_argument("--kinelo-ops-intake-url", default=first_env("KINELO_OPS_INTAKE_URL") or "")
    parser.add_argument("--kinelo-ops-intake-secret", default=first_env("KINELO_OPS_INTAKE_SECRET") or "")
    parser.add_argument("--discord-guild-id", default=first_env("HERMES_DISCORD_GUILD_ID", "DISCORD_GUILD_ID") or "")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        state_path = None if args.no_state else args.state_file
        state = load_state(state_path)
        processed = {str(value) for value in state.get("processedMessageIds", []) if str(value).strip()}
        messages = load_messages(args.messages_json, thread_id=args.thread_id, limit=args.limit, discord_token=args.discord_token)
        raw, source_message = extract_payload(
            messages,
            message_id=args.message_id,
            allow_plain=args.allow_plain,
            processed_message_ids=processed,
        )
        result = run_ingest(raw, args, source_message)
        if result.get("ok") and not args.dry_run:
            mark_processed(state, source_message, result)
            save_state(state_path, state)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result.get("ok") else 1
    except Exception as error:
        message = str(error)
        if "no ingestable Mission Control payload found in Discord messages" in message:
            print(
                json.dumps(
                    {
                        "ok": True,
                        "stage": "noop",
                        "message": "no ingestable payload found",
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 0
        print(json.dumps({"ok": False, "error": f"{type(error).__name__}: {error}"}, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
