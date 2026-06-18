#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
ALLOWED_ACTION_TYPES = {"desktop_hermes_prompt", "desktop_repo_sync_restart_smoke"}


def first_env(*names: str) -> str | None:
    for name in names:
        value = os.getenv(name, "").strip()
        if value:
            return value
    return None


def request_json(
    url: str,
    token: str | None,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    timeout_sec: int = 10,
) -> tuple[int, dict[str, Any] | str]:
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
        with urlopen(request, timeout=timeout_sec) as response:
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
    except TimeoutError as error:
        return 0, f"timeout: {error}"
    except URLError as error:
        return 0, str(error.reason)
    except OSError as error:
        return 0, f"{type(error).__name__}: {error}"


def compact(value: str, limit: int = 4000) -> str:
    return value if len(value) <= limit else value[-limit:]


def run_cmd(cmd: list[str], cwd: Path | None = None, timeout_sec: int = 180) -> dict[str, Any]:
    started = time.time()
    try:
        process = subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else None,
            text=True,
            capture_output=True,
            timeout=timeout_sec,
        )
        return {
            "cmd": " ".join(cmd),
            "exitCode": process.returncode,
            "durationSec": round(time.time() - started, 3),
            "stdout": compact(process.stdout or ""),
            "stderr": compact(process.stderr or ""),
        }
    except subprocess.TimeoutExpired as error:
        return {
            "cmd": " ".join(cmd),
            "exitCode": 124,
            "durationSec": round(time.time() - started, 3),
            "stdout": compact(error.stdout or "" if isinstance(error.stdout, str) else ""),
            "stderr": compact(error.stderr or "" if isinstance(error.stderr, str) else "timeout"),
        }


def smoke_url(url: str, token: str | None, timeout_sec: int = 30) -> dict[str, Any]:
    status, body = request_json(url, token, timeout_sec=timeout_sec)
    return {
        "url": url,
        "status": status,
        "ok": status == 200,
        "body": body if isinstance(body, dict) else str(body)[:1000],
    }


def safe_repo_path(value: str | None) -> Path:
    path = Path(value or ROOT).expanduser()
    resolved = path.resolve()
    if resolved.name != "physio-hermes-ops":
        raise ValueError(f"repoPath must resolve to physio-hermes-ops, got {resolved}")
    if not (resolved / ".git").exists():
        raise ValueError(f"repoPath is not a git worktree: {resolved}")
    return resolved


def safe_cwd(value: str | None) -> Path:
    path = Path(value or Path.home()).expanduser()
    resolved = path.resolve()
    home = Path.home().resolve()
    if resolved != home and home not in resolved.parents:
        raise ValueError(f"cwd must be under {home}, got {resolved}")
    if not resolved.exists() or not resolved.is_dir():
        raise ValueError(f"cwd is not a directory: {resolved}")
    return resolved


def bounded_timeout(value: Any, default: int = 600) -> int:
    try:
        timeout_sec = int(value)
    except Exception:
        timeout_sec = default
    return max(30, min(timeout_sec, 1800))


def resolve_hermes_bin(value: Any) -> str:
    requested = str(value or "").strip()
    env_requested = first_env("HERMES_CLI", "HERMES_BIN")
    candidates: list[str] = []
    if requested:
        candidates.append(requested)
    elif env_requested:
        candidates.append(env_requested)
    candidates.extend(
        [
            "hermes",
            str(Path.home() / ".local/bin/hermes"),
            "/home/yk/.local/bin/hermes",
            "/usr/local/bin/hermes",
            "/opt/homebrew/bin/hermes",
        ]
    )

    checked: list[str] = []
    for candidate in candidates:
        if not candidate or candidate in checked:
            continue
        checked.append(candidate)
        if "/" not in candidate:
            found = shutil.which(candidate)
            if found:
                return found
            continue
        path = Path(candidate).expanduser()
        if path.is_file() and os.access(path, os.X_OK):
            return str(path)

    raise FileNotFoundError(
        "Hermes CLI not found; set params.hermesBin or HERMES_CLI/HERMES_BIN. "
        f"Checked: {', '.join(checked)}"
    )


def execute_desktop_hermes_prompt(action: dict[str, Any]) -> dict[str, Any]:
    params = action.get("params") if isinstance(action.get("params"), dict) else {}
    prompt = str(params.get("prompt") or "").strip()
    if not prompt:
        raise ValueError("params.prompt is required")
    if len(prompt) > 8000:
        raise ValueError("params.prompt must be 8000 characters or fewer")

    cwd = safe_cwd(params.get("cwd"))
    timeout_sec = bounded_timeout(params.get("timeoutSec"))
    hermes_bin = resolve_hermes_bin(params.get("hermesBin"))
    command = [hermes_bin, "-z", prompt]
    result = run_cmd(command, cwd=cwd, timeout_sec=timeout_sec)
    return {
        "ok": result.get("exitCode") == 0,
        "cwd": str(cwd),
        "timeoutSec": timeout_sec,
        "promptPreview": compact(prompt, 500),
        "command": result,
    }


def execute_repo_sync_restart_smoke(action: dict[str, Any], token: str | None) -> dict[str, Any]:
    params = action.get("params") if isinstance(action.get("params"), dict) else {}
    repo_path = safe_repo_path(params.get("repoPath"))
    remote = str(params.get("remote") or "origin")
    branch = str(params.get("branch") or "main")
    service_name = str(params.get("serviceName") or "ops-control-api.service")
    expected_head = str(params.get("expectedHead") or "").strip()
    smoke_base_url = str(params.get("smokeBaseUrl") or "http://127.0.0.1:8792").rstrip("/")
    smoke_timeout_sec = bounded_timeout(params.get("smokeTimeoutSec"), default=30)
    smoke_paths = params.get("smokePaths")
    if not isinstance(smoke_paths, list) or not smoke_paths:
        smoke_paths = [
            "/health",
            "/plans?organizationId=org-smoke",
            "/tasks?organizationId=org-smoke",
            "/tasks/next?organizationId=org-smoke",
            "/snapshot?organizationId=org-smoke",
            "/mission-actions?organizationId=org-smoke&limit=1",
        ]

    commands = [
        ["git", "-C", str(repo_path), "rev-parse", "--short", "HEAD"],
        ["git", "-C", str(repo_path), "fetch", remote, branch],
        ["git", "-C", str(repo_path), "pull", "--ff-only", remote, branch],
        ["git", "-C", str(repo_path), "rev-parse", "--short", "HEAD"],
        ["systemctl", "--user", "restart", service_name],
    ]
    results = [run_cmd(command, timeout_sec=240) for command in commands]

    if expected_head:
        head_result = run_cmd(["git", "-C", str(repo_path), "rev-parse", "HEAD"], timeout_sec=30)
        results.append(head_result)
        actual_head = (head_result.get("stdout") or "").strip()
        if head_result.get("exitCode") != 0 or not actual_head.startswith(expected_head):
            return {
                "ok": False,
                "error": "expected_head_mismatch",
                "expectedHead": expected_head,
                "actualHead": actual_head,
                "commands": results,
                "smoke": [],
            }

    command_ok = all(item.get("exitCode") == 0 for item in results)
    time.sleep(float(params.get("restartDelaySec") or 1.0))
    smoke = [smoke_url(f"{smoke_base_url}{path}", token, timeout_sec=smoke_timeout_sec) for path in smoke_paths]
    smoke_ok = all(item["ok"] for item in smoke)

    return {
        "ok": command_ok and smoke_ok,
        "repoPath": str(repo_path),
        "remote": remote,
        "branch": branch,
        "serviceName": service_name,
        "smokeTimeoutSec": smoke_timeout_sec,
        "commands": results,
        "smoke": smoke,
    }


def mark_status(base_url: str, token: str | None, organization_id: str, action_id: str, status: str, result: dict[str, Any]) -> tuple[int, dict[str, Any] | str]:
    summary = "ok" if result.get("ok") else str(result.get("error") or "failed")
    return request_json(
        f"{base_url}/mission-actions/{action_id}/status",
        token,
        method="POST",
        payload={
            "organizationId": organization_id,
            "status": status,
            "result": summary,
            "resultData": result,
        },
    )


def mark_status_with_retry(
    base_url: str,
    token: str | None,
    organization_id: str,
    action_id: str,
    status: str,
    result: dict[str, Any],
    attempts: int = 6,
) -> tuple[int, dict[str, Any] | str]:
    last_status: int = 0
    last_body: dict[str, Any] | str = "not attempted"
    for attempt in range(attempts):
        last_status, last_body = mark_status(base_url, token, organization_id, action_id, status, result)
        if last_status == 200:
            return last_status, last_body
        time.sleep(min(2**attempt, 10))
    return last_status, last_body


def run_once(args: argparse.Namespace) -> int:
    base_url = args.base_url.rstrip("/")
    query = {
        "organizationId": args.organization_id,
        "targetAgent": args.target_agent,
    }
    if args.target_host:
        query["targetHost"] = args.target_host
    status, body = request_json(f"{base_url}/mission-actions/next?{urlencode(query)}", args.token)
    if status != 200 or not isinstance(body, dict):
        print(json.dumps({"ok": False, "stage": "next", "status": status, "response": body}, ensure_ascii=False, indent=2))
        return 1

    action = body.get("item") or body.get("data")
    if not action:
        print(json.dumps({"ok": True, "stage": "idle", "message": "no queued action"}, ensure_ascii=False, indent=2))
        return 0

    action_id = str(action.get("id") or "")
    action_type = str(action.get("actionType") or "")
    if action_type not in ALLOWED_ACTION_TYPES:
        result = {"ok": False, "error": "unsupported_action_type", "actionType": action_type}
        mark_status_with_retry(base_url, args.token, args.organization_id, action_id, "blocked", result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1

    claim_status, claim_body = request_json(
        f"{base_url}/mission-actions/{action_id}/claim",
        args.token,
        method="POST",
        payload={"organizationId": args.organization_id, "workerId": args.worker_id},
    )
    if claim_status != 200 or not isinstance(claim_body, dict):
        print(json.dumps({"ok": False, "stage": "claim", "status": claim_status, "response": claim_body}, ensure_ascii=False, indent=2))
        return 1

    claimed = claim_body.get("item") or claim_body.get("data") or action
    try:
        if action_type == "desktop_repo_sync_restart_smoke":
            result = execute_repo_sync_restart_smoke(claimed, args.token)
        elif action_type == "desktop_hermes_prompt":
            result = execute_desktop_hermes_prompt(claimed)
        else:
            result = {"ok": False, "error": "unsupported_action_type", "actionType": action_type}
    except Exception as error:
        result = {"ok": False, "error": f"{type(error).__name__}: {error}"}

    final_status = "done" if result.get("ok") else "failed"
    update_status, update_body = mark_status_with_retry(base_url, args.token, args.organization_id, action_id, final_status, result)
    output = {
        "ok": result.get("ok") is True and update_status == 200,
        "actionId": action_id,
        "finalStatus": final_status,
        "statusUpdate": {"status": update_status, "response": update_body},
        "result": result,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0 if output["ok"] else 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Poll and execute bounded Mission Control desktop actions.")
    parser.add_argument("--base-url", default=first_env("MISSION_CONTROL_BASE_URL", "HERMES_DESKTOP_MISSION_CONTROL_URL") or "http://127.0.0.1:8792")
    parser.add_argument(
        "--token",
        default=first_env(
            "MISSION_CONTROL_SHARED_TOKEN",
            "HERMES_MISSION_CONTROL_API_KEY",
            "OPS_CTL_TOKEN",
            "OPS_CTL_EXEC_ADMIN_TOKEN",
            "OPS_CTL_READ_TOKEN",
        ),
    )
    parser.add_argument("--organization-id", default=os.getenv("MISSION_CONTROL_ORGANIZATION_ID", "org-smoke"))
    parser.add_argument("--target-agent", default=os.getenv("MISSION_CONTROL_WORKER_AGENT", "desktop-hermes"))
    parser.add_argument("--target-host", default=os.getenv("MISSION_CONTROL_WORKER_HOST", "desktop-wsl"))
    parser.add_argument("--worker-id", default=os.getenv("MISSION_CONTROL_WORKER_ID", "desktop-hermes-action-worker"))
    return parser.parse_args()


def main() -> int:
    return run_once(parse_args())


if __name__ == "__main__":
    sys.exit(main())
