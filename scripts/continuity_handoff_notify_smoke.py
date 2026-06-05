#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]


def request_json(url: str, token: str | None, method: str = "GET", payload: dict[str, Any] | None = None) -> tuple[int, str]:
    headers = {"Accept": "application/json"}
    data = None
    if token:
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


def smoke_payload() -> dict[str, Any]:
    return {
        "schema": "continuity_handoff_v0_1",
        "source": {
            "surface": "codex-app",
            "runId": f"notify-smoke-{uuid.uuid4()}",
            "threadId": "manual-smoke",
            "repo": "Youngkwon-Lee/physio-hermes-ops",
            "branch": "codex/agent-os-runtime-split",
        },
        "goal": "Verify desktop Hermes continuity handoff notification",
        "done": ["MacBook emitted a smoke handoff notification"],
        "next": ["Desktop Hermes should persist the notification event"],
        "blockers": [],
        "memoryCandidates": [],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Probe desktop Hermes continuity handoff notification.")
    parser.add_argument("--base-url", default=os.getenv("HERMES_DESKTOP_MISSION_CONTROL_URL"), help="Example: http://100.83.147.56:8792")
    parser.add_argument("--token", default=os.getenv("HERMES_MISSION_CONTROL_API_KEY"), help="Optional x-hermes-api-key token.")
    parser.add_argument("--brain-dir", default=str(ROOT / ".runtime" / "notify-smoke-brain"), help="Temporary brain directory for smoke artifacts.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.base_url:
        print(json.dumps({"ok": False, "error": "--base-url or HERMES_DESKTOP_MISSION_CONTROL_URL is required"}, indent=2), file=sys.stderr)
        return 2
    base_url = args.base_url.rstrip("/")
    health_status, health_body = request_json(f"{base_url}/health", args.token)
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

    payload_path = ROOT / ".runtime" / "notify-smoke-payload.json"
    payload_path.parent.mkdir(parents=True, exist_ok=True)
    payload_path.write_text(json.dumps(smoke_payload(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

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
    completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)
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
