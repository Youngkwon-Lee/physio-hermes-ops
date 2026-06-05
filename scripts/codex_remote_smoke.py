#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


DEFAULT_CODEX_BINARY = "/Applications/Codex.app/Contents/Resources/codex"
DEFAULT_REMOTE_WORKDIR = "~/tmp/codex-smoke"
EXPECTED = "CODEX_REMOTE_SMOKE_OK"


class SmokeFailure(Exception):
    def __init__(self, failure_class: str, message: str) -> None:
        super().__init__(message)
        self.failure_class = failure_class


def now_ms() -> int:
    return int(time.time() * 1000)


def run_command(command: list[str], timeout: int) -> dict[str, Any]:
    started = now_ms()
    try:
        completed = subprocess.run(
            command,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
        return {
            "command": command,
            "exitCode": completed.returncode,
            "durationMs": now_ms() - started,
            "stdout": completed.stdout.strip(),
            "stderr": completed.stderr.strip(),
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "command": command,
            "exitCode": None,
            "durationMs": now_ms() - started,
            "stdout": (exc.stdout or "").strip() if isinstance(exc.stdout, str) else "",
            "stderr": (exc.stderr or "").strip() if isinstance(exc.stderr, str) else "timeout",
            "timeout": True,
        }


def quote_remote_script(script: str) -> str:
    return script


def build_shell_command(script: str, host: str | None) -> list[str]:
    if host:
        return [
            "ssh",
            "-o",
            "BatchMode=yes",
            "-o",
            "ConnectTimeout=10",
            host,
            quote_remote_script(script),
        ]
    return ["/bin/bash", "-lc", script]


def step_result(name: str, failure_class: str, script: str, host: str | None, timeout: int) -> dict[str, Any]:
    result = run_command(build_shell_command(script, host), timeout)
    result["name"] = name
    result["failureClass"] = failure_class
    result["passed"] = result["exitCode"] == 0
    return result


def require_step(step: dict[str, Any]) -> None:
    if step["passed"]:
        return
    detail = step.get("stderr") or step.get("stdout") or "command failed"
    raise SmokeFailure(step["failureClass"], f"{step['name']} failed: {detail}")


def compact(value: str, limit: int = 900) -> str:
    text = value.strip()
    if len(text) <= limit:
        return text
    return text[:limit] + "...[truncated]"


def shell_path(value: str) -> str:
    if value == "~":
        return "$HOME"
    if value.startswith("~/"):
        return "$HOME/" + shlex.quote(value[2:])
    return shlex.quote(value)


def make_result(status: str, target: dict[str, Any], steps: list[dict[str, Any]], failure: dict[str, str] | None) -> dict[str, Any]:
    return {
        "schema": "codex_remote_smoke_v0_1",
        "status": status,
        "target": target,
        "expected": EXPECTED,
        "failure": failure,
        "steps": [
            {
                "name": step["name"],
                "passed": step["passed"],
                "failureClass": step["failureClass"],
                "exitCode": step["exitCode"],
                "durationMs": step["durationMs"],
                "stdout": compact(step.get("stdout", "")),
                "stderr": compact(step.get("stderr", "")),
            }
            for step in steps
        ],
    }


def failure_hint(failure_class: str, message: str) -> str:
    text = message.lower()
    if failure_class == "transport_failure":
        if "could not resolve hostname" in text:
            return "SSH host alias is missing. Add a ~/.ssh/config Host entry or use the MacBook Tailscale/LAN hostname."
        if "connection refused" in text:
            return "SSH reached the host but port 22 is closed. Enable macOS Remote Login on the MacBook."
        if "permission denied" in text:
            return "SSH reached the host but key/password auth failed. Install the worker public key on the MacBook."
        return "Check SSH/Tailscale reachability from the Hermes host to the MacBook."
    if failure_class == "binary_failure":
        return "Verify the bundled Codex path exists: /Applications/Codex.app/Contents/Resources/codex."
    if failure_class == "exec_failure":
        return "Run Codex login/doctor on the MacBook and confirm non-interactive codex exec works."
    if failure_class == "artifact_failure":
        return "Verify the throwaway workdir is writable and codex exec can create result.md there."
    return "Inspect stdout/stderr and keep the run in dry-run until resolved."


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def post_to_mission_control(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    if not args.mission_control_url and not args.mission_run_id:
        return
    if not args.mission_control_url:
        raise SmokeFailure("artifact_failure", "--mission-control-url is required when --mission-run-id is set")
    if not args.mission_run_id:
        raise SmokeFailure("artifact_failure", "--mission-run-id is required when --mission-control-url is set")

    base_url = args.mission_control_url.rstrip("/")
    url = f"{base_url}/runs/{args.mission_run_id}/codex-bridge/smoke-result"
    body = {
        "organizationId": args.organization_id,
        "result": payload,
    }
    headers = {"Content-Type": "application/json"}
    if args.mission_control_api_key:
        headers["x-hermes-api-key"] = args.mission_control_api_key

    request = Request(
        url,
        method="POST",
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers=headers,
    )
    try:
        with urlopen(request, timeout=args.mission_control_timeout) as response:
            if response.status < 200 or response.status >= 300:
                raise SmokeFailure("artifact_failure", f"Mission Control post failed: HTTP {response.status}")
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise SmokeFailure("artifact_failure", f"Mission Control post failed: HTTP {exc.code}: {detail}") from exc
    except URLError as exc:
        raise SmokeFailure("artifact_failure", f"Mission Control post failed: {exc.reason}") from exc


def persist_and_publish(args: argparse.Namespace, payload: dict[str, Any]) -> bool:
    if args.json_out:
        write_json(args.json_out, payload)
    try:
        post_to_mission_control(args, payload)
        return True
    except SmokeFailure as exc:
        print(json.dumps({"missionControlPost": "fail", "message": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return False


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Smoke test a local or SSH Codex CLI worker.")
    parser.add_argument("--host", default=os.getenv("CODEX_REMOTE_HOST"), help="SSH host alias, for example macbook.")
    parser.add_argument("--local", action="store_true", help="Run directly on this machine instead of SSH.")
    parser.add_argument("--codex", default=os.getenv("CODEX_REMOTE_BINARY", DEFAULT_CODEX_BINARY))
    parser.add_argument("--workdir", default=os.getenv("CODEX_REMOTE_WORKDIR", DEFAULT_REMOTE_WORKDIR))
    parser.add_argument("--json-out", type=Path, default=None)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--mission-control-url", default=os.getenv("HERMES_MISSION_CONTROL_URL"))
    parser.add_argument("--mission-run-id", default=os.getenv("HERMES_MISSION_RUN_ID"))
    parser.add_argument("--organization-id", default=os.getenv("HERMES_ORGANIZATION_ID", "default"))
    parser.add_argument("--mission-control-api-key", default=os.getenv("HERMES_MISSION_CONTROL_API_KEY"))
    parser.add_argument("--mission-control-timeout", type=int, default=10)
    parser.add_argument(
        "--health-only",
        action="store_true",
        help="Run transport and binary checks only. Does not call codex exec.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    host = None if args.local else args.host
    codex = args.codex
    workdir = args.workdir
    steps: list[dict[str, Any]] = []
    target = {
        "host": host or "local",
        "codex": codex,
        "workdir": workdir,
        "healthOnly": bool(args.health_only),
    }

    try:
        transport_script = "hostname && uname -a && whoami"
        step = step_result("transport", "transport_failure", transport_script, host, 30)
        steps.append(step)
        require_step(step)

        binary_script = f"{shlex.quote(codex)} --version && {shlex.quote(codex)} --help | head -40"
        step = step_result("binary", "binary_failure", binary_script, host, 30)
        steps.append(step)
        require_step(step)

        if not args.health_only:
            exec_prompt = "Print exactly: CODEX_REMOTE_SMOKE_OK"
            exec_script = (
                f"{shlex.quote(codex)} exec "
                f"--sandbox read-only "
                f"--ephemeral "
                f"--skip-git-repo-check "
                f"{shlex.quote(exec_prompt)}"
            )
            step = step_result("exec", "exec_failure", exec_script, host, args.timeout)
            steps.append(step)
            require_step(step)
            if EXPECTED not in step.get("stdout", ""):
                raise SmokeFailure("exec_failure", "exec output did not contain expected marker")

            artifact_prompt = f"Create a file named result.md containing exactly {EXPECTED}"
            artifact_script = (
                f"mkdir -p {shell_path(workdir)} && "
                f"cd {shell_path(workdir)} && "
                "rm -f result.md && "
                f"{shlex.quote(codex)} exec "
                f"--sandbox workspace-write "
                f"--ephemeral "
                f"--skip-git-repo-check "
                f"{shlex.quote(artifact_prompt)} && "
                "cat result.md"
            )
            step = step_result("artifact", "artifact_failure", artifact_script, host, args.timeout)
            steps.append(step)
            require_step(step)
            if EXPECTED not in step.get("stdout", ""):
                raise SmokeFailure("artifact_failure", "result.md did not contain expected marker")

        payload = make_result("pass", target, steps, None)
        published = persist_and_publish(args, payload)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0 if published else 2
    except SmokeFailure as exc:
        payload = make_result(
            "fail",
            target,
            steps,
            {
                "class": exc.failure_class,
                "message": str(exc),
                "hint": failure_hint(exc.failure_class, str(exc)),
            },
        )
        persist_and_publish(args, payload)
        print(json.dumps(payload, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
