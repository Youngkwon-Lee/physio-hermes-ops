#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]


def first_env(*names: str) -> str | None:
    for name in names:
        value = os.getenv(name, "").strip()
        if value:
            return value
    return None


def request_json(url: str, token: str | None, method: str = "GET", payload: dict[str, Any] | None = None) -> tuple[int, str]:
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
        with urlopen(request, timeout=5) as response:
            return response.status, response.read().decode("utf-8", errors="replace")
    except HTTPError as error:
        return error.code, error.read().decode("utf-8", errors="replace")
    except URLError as error:
        return 0, str(error.reason)


def iso_expiry(minutes: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(minutes=minutes)).isoformat(timespec="seconds")


def smoke_payload(args: argparse.Namespace) -> dict[str, Any]:
    if args.schema == "continuity_a2a_lite_v0_1":
        conversation_id = args.conversation_id or f"conv-{uuid.uuid4()}"
        message_id = args.message_id or f"msg-{uuid.uuid4().hex[:8]}"
        payload = {
            "schema": args.schema,
            "conversationId": conversation_id,
            "messageId": message_id,
            "replyTo": args.reply_to,
            "role": args.role,
            "from": {
                "agent": args.from_agent or args.surface,
                "surface": args.from_surface,
                "host": args.from_host,
            },
            "to": {
                "agent": args.to_agent,
                "surface": args.to_surface,
                "host": args.to_host,
            },
            "goal": args.goal,
            "message": {
                "text": args.message_text or args.goal,
                "artifacts": [],
                "structured": {},
            },
            "control": {
                "turnIndex": args.turn_index,
                "turnLimit": args.turn_limit,
                "expiresAt": args.expires_at or iso_expiry(args.expires_in_minutes),
                "expectReply": not args.no_expect_reply,
                "replyMode": "callback",
            },
            "context": {
                "repo": args.repo,
                "branch": args.branch,
                "threadId": args.thread_id,
            },
            "ts": int(time.time()),
        }
        if args.clarification_question:
            payload["message"]["structured"]["clarification_question"] = args.clarification_question
        if args.answer_text:
            payload["message"]["structured"]["answer"] = args.answer_text
        if args.callback_url:
            payload["callback"] = {"url": args.callback_url}
            if args.callback_token:
                payload["callback"]["token"] = args.callback_token
        return payload

    run_id = args.run_id.strip() if args.run_id else f"notify-smoke-{uuid.uuid4()}"
    return {
        "schema": "continuity_handoff_v0_1",
        "source": {
            "surface": args.surface,
            "runId": run_id,
            "threadId": args.thread_id,
            "repo": args.repo,
            "branch": args.branch,
        },
        "goal": args.goal,
        "done": ["MacBook emitted a smoke handoff notification"],
        "next": ["Desktop Hermes should persist the notification event"],
        "blockers": [],
        "memoryCandidates": [],
        "ts": int(time.time()),
        **({"callbackUrl": args.callback_url} if args.callback_url else {}),
    }


def verbose_print(enabled: bool, payload: dict[str, Any]) -> None:
    if enabled:
        print(json.dumps(payload, ensure_ascii=False, indent=2), file=sys.stderr)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Probe desktop Hermes continuity handoff notification.")
    parser.add_argument(
        "--base-url",
        default=first_env("MISSION_CONTROL_BASE_URL", "HERMES_DESKTOP_MISSION_CONTROL_URL"),
        help="Example: http://100.83.147.56:8792",
    )
    parser.add_argument(
        "--token",
        default=first_env("MISSION_CONTROL_SHARED_TOKEN", "HERMES_MISSION_CONTROL_API_KEY"),
        help="Optional shared API token. Sent as Authorization: Bearer and x-hermes-api-key.",
    )
    parser.add_argument("--callback-url", default=None, help="Optional callback receiver URL to include in the handoff event.")
    parser.add_argument("--callback-token", default=None, help="Optional callback token for A2A-lite callback delivery.")
    parser.add_argument("--surface", default="codex-app", help="source.surface value for the smoke payload.")
    parser.add_argument("--run-id", default=None, help="source.runId value for the smoke payload.")
    parser.add_argument("--thread-id", default="manual-smoke", help="thread id metadata for handoff/A2A payloads.")
    parser.add_argument("--repo", default="Youngkwon-Lee/physio-hermes-ops", help="repo metadata for handoff/A2A payloads.")
    parser.add_argument("--branch", default="codex/agent-os-runtime-split", help="branch metadata for handoff/A2A payloads.")
    parser.add_argument("--goal", default="Verify desktop Hermes continuity handoff notification", help="goal value for the smoke payload.")
    parser.add_argument("--verbose", action="store_true", help="Print health, payload, and subprocess details to stderr.")
    parser.add_argument("--brain-dir", default=str(ROOT / ".runtime" / "notify-smoke-brain"), help="Temporary brain directory for smoke artifacts.")
    parser.add_argument("--schema", default="continuity_handoff_v0_1", help="Payload schema. Use continuity_a2a_lite_v0_1 for bounded A2A-lite.")
    parser.add_argument("--conversation-id", default=None, help="A2A-lite conversationId.")
    parser.add_argument("--message-id", default=None, help="A2A-lite messageId.")
    parser.add_argument("--reply-to", default=None, help="A2A-lite replyTo message id.")
    parser.add_argument("--role", default="request", help="A2A-lite role: request, answer, question, result, blocked, cancelled.")
    parser.add_argument("--message-text", default=None, help="A2A-lite message.text value.")
    parser.add_argument("--clarification-question", default=None, help="Optional A2A-lite structured clarification question.")
    parser.add_argument("--answer-text", default=None, help="Optional A2A-lite structured answer text.")
    parser.add_argument("--turn-index", type=int, default=1, help="A2A-lite control.turnIndex.")
    parser.add_argument("--turn-limit", type=int, default=4, help="A2A-lite control.turnLimit.")
    parser.add_argument("--expires-at", default=None, help="A2A-lite control.expiresAt.")
    parser.add_argument("--expires-in-minutes", type=int, default=15, help="A2A-lite expiry offset when --expires-at is omitted.")
    parser.add_argument("--no-expect-reply", action="store_true", help="Set A2A-lite control.expectReply to false.")
    parser.add_argument("--from-agent", default=None, help="A2A-lite from.agent override.")
    parser.add_argument("--from-surface", default="codex-cli", help="A2A-lite from.surface.")
    parser.add_argument("--from-host", default="macbook", help="A2A-lite from.host.")
    parser.add_argument("--to-agent", default="desktop-hermes", help="A2A-lite to.agent.")
    parser.add_argument("--to-surface", default="hermes-gateway", help="A2A-lite to.surface.")
    parser.add_argument("--to-host", default="desktop-wsl", help="A2A-lite to.host.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.base_url:
        print(
            json.dumps(
                {"ok": False, "error": "--base-url or MISSION_CONTROL_BASE_URL or HERMES_DESKTOP_MISSION_CONTROL_URL is required"},
                indent=2,
            ),
            file=sys.stderr,
        )
        return 2
    base_url = args.base_url.rstrip("/")
    verbose_print(args.verbose, {"stage": "health_request", "url": f"{base_url}/health"})
    health_status, health_body = request_json(f"{base_url}/health", args.token)
    verbose_print(args.verbose, {"stage": "health_response", "status": health_status, "body": health_body[:500]})
    if health_status != 200:
        print(
            json.dumps(
                {
                    "ok": False,
                    "stage": "health",
                    "status": health_status,
                    "body": health_body[:500],
                    "hint": "Start apps/api/mission_control_api.py on the desktop Hermes host and expose the selected port.",
                },
                ensure_ascii=False,
                indent=2,
            ),
            file=sys.stderr,
        )
        return 1

    payload = smoke_payload(args)
    payload_path = ROOT / ".runtime" / "notify-smoke-payload.json"
    payload_path.parent.mkdir(parents=True, exist_ok=True)
    payload_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    verbose_print(args.verbose, {"stage": "payload", "path": str(payload_path), "payload": payload})

    if args.schema == "continuity_a2a_lite_v0_1":
        status, body = request_json(f"{base_url}/handoff/notify", args.token, method="POST", payload=payload)
        parsed_body: dict[str, Any] | str
        try:
            parsed_body = json.loads(body) if body else {}
        except json.JSONDecodeError:
            parsed_body = body
        ok = status == 200 and isinstance(parsed_body, dict) and parsed_body.get("ok") is True
        result = {"ok": ok, "healthStatus": health_status, "status": status, "response": parsed_body, "payload": payload}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if ok else 1

    command = [
        sys.executable,
        str(ROOT / "scripts" / "capture_continuity_handoff.py"),
        "--input",
        str(payload_path),
        "--brain-dir",
        args.brain_dir,
        "--notify-url",
        f"{base_url}/handoff/notify",
    ]
    if args.token:
        command.extend(["--notify-token", args.token])
    verbose_print(args.verbose, {"stage": "subprocess", "command": command})
    completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)
    verbose_print(
        args.verbose,
        {
            "stage": "subprocess_result",
            "returncode": completed.returncode,
            "stdout": completed.stdout[:4000],
            "stderr": completed.stderr[:4000],
        },
    )
    if completed.returncode != 0:
        print(completed.stdout, end="")
        print(completed.stderr, end="", file=sys.stderr)
        return completed.returncode
    result = json.loads(completed.stdout)
    notification = result.get("notification") or {}
    ok = bool(notification.get("ok"))
    print(json.dumps({"ok": ok, "healthStatus": health_status, "capture": result}, ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
