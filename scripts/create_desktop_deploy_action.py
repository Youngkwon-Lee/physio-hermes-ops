#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import uuid
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


DEFAULT_SMOKE_PATHS = [
    "/health",
    "/plans?organizationId=org-smoke",
    "/tasks?organizationId=org-smoke",
    "/tasks/next?organizationId=org-smoke",
    "/snapshot?organizationId=org-smoke",
    "/mission-actions?organizationId=org-smoke&limit=1",
]


def first_env(*names: str) -> str | None:
    for name in names:
        value = os.getenv(name, "").strip()
        if value:
            return value
    return None


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


def git_head() -> str | None:
    process = subprocess.run(["git", "rev-parse", "HEAD"], text=True, capture_output=True)
    return process.stdout.strip() if process.returncode == 0 else None


def create_action_payload(args: argparse.Namespace) -> dict[str, Any]:
    params = {
        "repoPath": args.desktop_repo_path,
        "remote": args.remote,
        "branch": args.branch,
        "serviceName": args.service_name,
        "smokeBaseUrl": args.smoke_base_url,
        "smokePaths": args.smoke_path,
    }
    if args.expected_head:
        params["expectedHead"] = args.expected_head
    return {
        "organizationId": args.organization_id,
        "actionType": "desktop_repo_sync_restart_smoke",
        "title": args.title,
        "target": {
            "agent": "desktop-hermes",
            "surface": "hermes-gateway",
            "host": args.target_host,
        },
        "repo": args.repo,
        "priority": args.priority,
        "params": params,
        "sourceThread": {
            "channelName": "second_memory",
            "threadName": "맥북코덱스소통채널",
            "threadId": args.thread_id,
        },
        "tags": ["mission-control", "desktop-deploy", "action-worker"],
    }


def fallback_handoff_payload(args: argparse.Namespace, action_payload: dict[str, Any]) -> dict[str, Any]:
    fallback_id = f"handoff-{uuid.uuid4()}"
    return {
        "organizationId": args.organization_id,
        "id": fallback_id,
        "from": {"agent": "macbook-codex", "surface": "codex-app", "host": "macbook"},
        "to": {"agent": "desktop-hermes", "surface": "discord", "host": args.target_host},
        "repo": args.repo,
        "goal": "Bootstrap Mission Control action worker on desktop live",
        "context": (
            f"MacBook requested deploy action for {args.repo} {args.branch}, but /mission-actions is not available "
            "on desktop live. Desktop is still pre-bootstrap/old code."
        ),
        "expectedOutput": (
            "Run git pull --ff-only origin main, restart ops-control-api.service, enable "
            "mission-control-action-worker.timer, then verify /mission-actions returns 200."
        ),
        "sourceThread": action_payload["sourceThread"],
        "status": "waiting_for_codex",
        "tags": ["mission-control", "action-worker", "bootstrap"],
    }


def notify_payload(handoff: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    return {
        "schema": "continuity_handoff_v0_1",
        "handoffId": handoff["id"],
        "source": {
            "surface": "macbook-codex",
            "runId": f"deploy-action-fallback-{int(time.time())}",
            "threadId": args.thread_id,
            "repo": args.repo,
            "branch": args.branch,
        },
        "goal": handoff["goal"],
        "done": ["MacBook created a fallback bootstrap handoff because /mission-actions is not live yet."],
        "next": [
            "Desktop: git pull --ff-only origin main",
            "Desktop: systemctl --user restart ops-control-api.service",
            "Desktop: enable mission-control-action-worker.timer",
            "Verify /mission-actions returns 200",
        ],
        "blockers": ["Mission Control action queue is not deployed on desktop live yet."],
        "ts": int(time.time()),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a bounded desktop deploy action, with bootstrap handoff fallback.")
    parser.add_argument("--base-url", default=first_env("MISSION_CONTROL_BASE_URL", "HERMES_DESKTOP_MISSION_CONTROL_URL") or "http://100.83.147.56:8792")
    parser.add_argument("--token", default=first_env("MISSION_CONTROL_SHARED_TOKEN", "HERMES_MISSION_CONTROL_API_KEY") or "dev-local-mission-control")
    parser.add_argument("--organization-id", default="org-smoke")
    parser.add_argument("--repo", default="Youngkwon-Lee/physio-hermes-ops")
    parser.add_argument("--branch", default="main")
    parser.add_argument("--remote", default="origin")
    parser.add_argument("--desktop-repo-path", default="/home/yk/physio-hermes-ops")
    parser.add_argument("--service-name", default="ops-control-api.service")
    parser.add_argument("--smoke-base-url", default="http://127.0.0.1:8792")
    parser.add_argument("--smoke-path", action="append", default=DEFAULT_SMOKE_PATHS)
    parser.add_argument("--target-host", default="desktop-wsl")
    parser.add_argument("--thread-id", default="1515296585410416931")
    parser.add_argument("--title", default="Deploy latest physio-hermes-ops main to desktop live")
    parser.add_argument("--priority", type=int, default=10)
    parser.add_argument("--expected-head", default=git_head())
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    base_url = args.base_url.rstrip("/")
    action_payload = create_action_payload(args)
    status, body = request_json(f"{base_url}/mission-actions", args.token, method="POST", payload=action_payload)
    if status == 200:
        print(json.dumps({"ok": True, "mode": "mission_action", "status": status, "response": body}, ensure_ascii=False, indent=2))
        return 0
    if status != 404:
        print(json.dumps({"ok": False, "mode": "mission_action", "status": status, "response": body}, ensure_ascii=False, indent=2))
        return 1

    handoff_payload = fallback_handoff_payload(args, action_payload)
    handoff_status, handoff_body = request_json(f"{base_url}/handoffs", args.token, method="POST", payload=handoff_payload)
    notify_status = None
    notify_body: dict[str, Any] | str | None = None
    if handoff_status == 200:
        notify_status, notify_body = request_json(
            f"{base_url}/handoff/notify",
            args.token,
            method="POST",
            payload=notify_payload(handoff_payload, args),
        )
    ok = handoff_status == 200 and notify_status == 200
    print(json.dumps({
        "ok": ok,
        "mode": "bootstrap_handoff_fallback",
        "missionActionStatus": status,
        "handoff": {"status": handoff_status, "response": handoff_body},
        "notify": {"status": notify_status, "response": notify_body},
    }, ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
