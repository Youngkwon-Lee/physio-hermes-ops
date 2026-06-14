#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


DEFAULT_SOURCE_THREAD = {
    "channelName": "second_memory",
    "threadName": "맥북코덱스소통채널",
    "threadId": "1515296585410416931",
}


def first_env(*names: str) -> str | None:
    for name in names:
        value = os.getenv(name, "").strip()
        if value:
            return value
    return None


def compact(value: Any, limit: int = 1200) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    return text if len(text) <= limit else text[: limit - 1] + "…"


def request_json(url: str, token: str | None, method: str = "GET", payload: dict[str, Any] | None = None) -> tuple[int, dict[str, Any] | str]:
    headers = {"Accept": "application/json"}
    data = None
    if token:
        headers["Authorization"] = f"Bearer {token}"
        headers["x-hermes-api-key"] = token
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = Request(url, headers=headers, data=data, method=method)
    try:
        with urlopen(request, timeout=10) as response:
            body = response.read().decode("utf-8", errors="replace")
            try:
                return response.status, json.loads(body) if body else {}
            except json.JSONDecodeError:
                return response.status, body
    except HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        try:
            return error.code, json.loads(body) if body else {}
        except json.JSONDecodeError:
            return error.code, body
    except URLError as error:
        return 0, str(error.reason)


def load_input(path: str | None) -> str:
    if path and path != "-":
        return Path(path).read_text(encoding="utf-8")
    return sys.stdin.read()


def strip_checkbox(line: str) -> str:
    return re.sub(r"^\s*(?:[-*]|\d+[.)])\s*(?:\[[ xX]\]\s*)?", "", line).strip()


def parse_markdown(text: str) -> dict[str, Any]:
    lines = [line.rstrip() for line in text.splitlines()]
    title = next((line.lstrip("# ").strip() for line in lines if line.strip().startswith("#")), "")
    if not title:
        title = "Discord/Hermes meeting plan"

    task_lines: list[str] = []
    summary_lines: list[str] = []
    in_tasks = False
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if re.match(r"^#{1,6}\s*(tasks|todo|next|action|할 일|다음|액션)", stripped, flags=re.I):
            in_tasks = True
            continue
        if stripped.startswith("#"):
            if in_tasks:
                in_tasks = False
            continue
        if in_tasks and re.match(r"^\s*(?:[-*]|\d+[.)])\s*(?:\[[ xX]\]\s*)?", line):
            task_lines.append(strip_checkbox(line))
        elif not in_tasks:
            summary_lines.append(stripped)

    tasks = []
    for index, line in enumerate(task_lines[:20], start=1):
        assignee = "desktop-hermes"
        match = re.match(r"^\[([^\]]+)\]\s*(.+)$", line)
        if match:
            assignee = match.group(1).strip() or assignee
            line = match.group(2).strip()
        title_part, _, expected = line.partition("::")
        tasks.append(
            {
                "title": title_part.strip() or f"Meeting action {index}",
                "context": line,
                "expectedOutput": expected.strip() or "Complete the meeting action and update Mission Control.",
                "assignee": {"agent": assignee, "surface": "discord", "host": "desktop-wsl"},
                "priority": index * 10,
                "status": "ready",
            }
        )

    return {
        "title": title,
        "summary": "\n".join(summary_lines[:20]) or title,
        "horizon": "short",
        "tasks": tasks,
    }


def parse_payload(raw: str) -> dict[str, Any]:
    raw = raw.strip()
    if not raw:
        raise ValueError("input is empty")
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        parsed = parse_markdown(raw)
    if not isinstance(parsed, dict):
        raise ValueError("input must be a JSON object or markdown meeting note")
    return parsed


def normalize_source_thread(payload: dict[str, Any], args: argparse.Namespace) -> dict[str, str | None]:
    source = payload.get("sourceThread") or payload.get("source_thread") or {}
    if not isinstance(source, dict):
        source = {}
    return {
        "channelName": str(source.get("channelName") or args.channel_name or DEFAULT_SOURCE_THREAD["channelName"]).strip() or None,
        "threadName": str(source.get("threadName") or args.thread_name or DEFAULT_SOURCE_THREAD["threadName"]).strip() or None,
        "threadId": str(source.get("threadId") or args.thread_id or DEFAULT_SOURCE_THREAD["threadId"]).strip() or None,
        "url": str(source.get("url") or "").strip() or None,
    }


def normalize_task(task: dict[str, Any], *, args: argparse.Namespace, plan_id: str, source_thread: dict[str, Any], index: int) -> dict[str, Any]:
    assignee = task.get("assignee") if isinstance(task.get("assignee"), dict) else {}
    return {
        "organizationId": args.organization_id,
        "planId": plan_id,
        "title": compact(task.get("title") or task.get("goal") or f"Meeting action {index}", 300),
        "context": compact(task.get("context") or task.get("summary"), 1200),
        "expectedOutput": compact(task.get("expectedOutput") or task.get("expected_output") or task.get("result") or "Complete this meeting action.", 800),
        "assignee": {
            "agent": str(assignee.get("agent") or task.get("assigneeAgent") or args.default_assignee).strip(),
            "surface": str(assignee.get("surface") or task.get("assigneeSurface") or "discord").strip(),
            "host": str(assignee.get("host") or task.get("assigneeHost") or "desktop-wsl").strip(),
        },
        "repo": str(task.get("repo") or args.repo).strip() or None,
        "sourceThread": source_thread,
        "priority": int(task.get("priority") or index * 10),
        "status": str(task.get("status") or "ready").strip(),
        "tags": [str(tag).strip() for tag in task.get("tags", []) if str(tag).strip()] if isinstance(task.get("tags"), list) else ["discord", "meeting"],
    }


def build_plan_payload(payload: dict[str, Any], args: argparse.Namespace, source_thread: dict[str, Any]) -> dict[str, Any]:
    plan = payload.get("plan") if isinstance(payload.get("plan"), dict) else payload
    return {
        "organizationId": args.organization_id,
        "title": compact(plan.get("title") or plan.get("goal") or "Discord/Hermes meeting plan", 300),
        "horizon": str(plan.get("horizon") or payload.get("horizon") or "short").strip(),
        "status": str(plan.get("status") or payload.get("status") or "ready").strip(),
        "summary": compact(plan.get("summary") or plan.get("context") or payload.get("summary") or payload.get("context"), 1200),
        "owner": plan.get("owner") if isinstance(plan.get("owner"), dict) else {"agent": args.default_owner, "surface": "operator", "host": "desktop-wsl"},
        "sourceThread": source_thread,
        "priority": int(plan.get("priority") or payload.get("priority") or 50),
        "tags": [str(tag).strip() for tag in plan.get("tags", payload.get("tags", ["discord", "meeting"])) if str(tag).strip()]
        if isinstance(plan.get("tags", payload.get("tags", [])), list)
        else ["discord", "meeting"],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ingest a Discord/Hermes meeting summary into Mission Control plans and tasks.")
    parser.add_argument("--base-url", default=first_env("MISSION_CONTROL_BASE_URL", "HERMES_DESKTOP_MISSION_CONTROL_URL") or "http://100.83.147.56:8792")
    parser.add_argument("--token", default=first_env("MISSION_CONTROL_SHARED_TOKEN", "HERMES_MISSION_CONTROL_API_KEY") or "dev-local-mission-control")
    parser.add_argument("--input", "-i", default="-", help="JSON or markdown meeting note path. Use - for stdin.")
    parser.add_argument("--organization-id", default="org-smoke")
    parser.add_argument("--repo", default="Youngkwon-Lee/physio-hermes-ops")
    parser.add_argument("--thread-id", default=DEFAULT_SOURCE_THREAD["threadId"])
    parser.add_argument("--thread-name", default=DEFAULT_SOURCE_THREAD["threadName"])
    parser.add_argument("--channel-name", default=DEFAULT_SOURCE_THREAD["channelName"])
    parser.add_argument("--default-owner", default="youngkwon")
    parser.add_argument("--default-assignee", default="desktop-hermes")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        payload = parse_payload(load_input(args.input))
        source_thread = normalize_source_thread(payload, args)
        tasks_raw = payload.get("tasks") or payload.get("actions") or []
        if not isinstance(tasks_raw, list):
            raise ValueError("tasks must be a list")
        plan_payload = build_plan_payload(payload, args, source_thread)
        preview_tasks = [
            normalize_task(task if isinstance(task, dict) else {"title": str(task)}, args=args, plan_id="<created-plan-id>", source_thread=source_thread, index=index)
            for index, task in enumerate(tasks_raw, start=1)
        ]
        if args.dry_run:
            print(json.dumps({"ok": True, "dryRun": True, "plan": plan_payload, "tasks": preview_tasks}, ensure_ascii=False, indent=2))
            return 0

        base_url = args.base_url.rstrip("/")
        status, plan_body = request_json(f"{base_url}/plans", args.token, method="POST", payload=plan_payload)
        if status != 200 or not isinstance(plan_body, dict) or not plan_body.get("ok"):
            print(json.dumps({"ok": False, "stage": "create_plan", "status": status, "response": plan_body}, ensure_ascii=False, indent=2))
            return 1
        plan = plan_body.get("item") or plan_body.get("data") or {}
        plan_id = str(plan.get("id") or "")
        created_tasks = []
        for index, task in enumerate(tasks_raw, start=1):
            task_payload = normalize_task(
                task if isinstance(task, dict) else {"title": str(task)},
                args=args,
                plan_id=plan_id,
                source_thread=source_thread,
                index=index,
            )
            task_status, task_body = request_json(f"{base_url}/tasks", args.token, method="POST", payload=task_payload)
            created_tasks.append({"status": task_status, "response": task_body})
            if task_status != 200 or not isinstance(task_body, dict) or not task_body.get("ok"):
                print(json.dumps({"ok": False, "stage": "create_task", "plan": plan, "tasks": created_tasks}, ensure_ascii=False, indent=2))
                return 1

        print(
            json.dumps(
                {
                    "ok": True,
                    "plan": plan,
                    "tasks": [(row["response"].get("item") or row["response"].get("data")) for row in created_tasks],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    except Exception as error:
        print(json.dumps({"ok": False, "error": f"{type(error).__name__}: {error}"}, ensure_ascii=False, indent=2))
        return 1


if __name__ == "__main__":
    sys.exit(main())
