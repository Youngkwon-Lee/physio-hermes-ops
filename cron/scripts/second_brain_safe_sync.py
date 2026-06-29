#!/usr/bin/env python3
"""Safe second-brain sync watchdog.

Silent-by-default no_agent cron script.

It fetches the configured remote and only runs `git pull --ff-only` when the
working tree is clean and the local branch is strictly behind upstream. Dirty,
ahead, diverged, or validation-failed states are reported and left untouched.
"""

from __future__ import annotations

import os
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_BRAIN_DIR = Path(os.environ.get("SECOND_BRAIN_DIR", "/home/yk/brain-linux"))
REMOTE = os.environ.get("SECOND_BRAIN_REMOTE", "origin")
BRANCH = os.environ.get("SECOND_BRAIN_BRANCH", "main")
STATUS_LIMIT = int(os.environ.get("SECOND_BRAIN_SYNC_STATUS_LIMIT", "30"))
REPEAT_HOURS = float(os.environ.get("SECOND_BRAIN_SYNC_REPEAT_HOURS", "24"))
STATE_PATH = Path(
    os.environ.get(
        "SECOND_BRAIN_SYNC_STATE_PATH",
        str(Path.home() / ".local/state/physio-hermes-ops/second_brain_safe_sync_state.json"),
    )
)


def run(command: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, capture_output=True, text=True)


def compact(text: str, limit: int = 1600) -> str:
    text = "\n".join(line.rstrip() for line in text.strip().splitlines())
    if len(text) <= limit:
        return text
    return text[: limit - 40].rstrip() + "\n... [truncated]"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def parse_time(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def load_state() -> dict[str, object]:
    try:
        return json.loads(STATE_PATH.read_text())
    except Exception:
        return {}


def save_state(state: dict[str, object]) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n")


def signature(title: str, lines: list[str]) -> str:
    payload = "\n".join([title, *lines]).encode("utf-8", errors="replace")
    return hashlib.sha256(payload).hexdigest()


def should_emit(title: str, lines: list[str]) -> bool:
    state = load_state()
    sig = signature(title, lines)
    last_sig = state.get("last_issue_signature")
    last_at = parse_time(state.get("last_issue_at"))
    now = utc_now()
    emit = sig != last_sig
    if not emit and last_at is not None:
        emit = (now - last_at).total_seconds() >= REPEAT_HOURS * 3600
    if emit:
        state["last_issue_signature"] = sig
        state["last_issue_at"] = now.isoformat()
        state["last_issue_status"] = title
        save_state(state)
    return emit


def mark_ok() -> None:
    state = load_state()
    state["last_ok_at"] = utc_now().isoformat()
    state.pop("last_issue_signature", None)
    state.pop("last_issue_status", None)
    save_state(state)


def issue(title: str, lines: list[str]) -> None:
    if should_emit(title, lines):
        print("\n".join(["[Second Brain Safe Sync]", f"status: {title}", *lines]))


def git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return run(["git", *args], cwd=repo)


def porcelain(repo: Path) -> list[str]:
    result = git(repo, "status", "--porcelain")
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout).strip() or "git status failed")
    return result.stdout.splitlines()


def upstream_counts(repo: Path) -> tuple[int, int]:
    result = git(repo, "rev-list", "--left-right", "--count", "HEAD...@{upstream}")
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout).strip() or "upstream not configured")
    left, right = result.stdout.strip().split()[:2]
    return int(left), int(right)


def validation_commands(repo: Path) -> list[list[str]]:
    commands: list[list[str]] = []
    lint = repo / "operations" / "tools" / "brain_lint.py"
    if lint.exists():
        commands.append(["python3", str(lint)])
    commands.append(["git", "-C", str(repo), "diff", "--check"])
    return commands


def validate(repo: Path) -> list[str]:
    failures: list[str] = []
    for command in validation_commands(repo):
        result = run(command, cwd=repo)
        if result.returncode != 0:
            failures.append(
                "$ "
                + " ".join(command)
                + f"\nexit: {result.returncode}\n"
                + compact(result.stdout + result.stderr, 1200)
            )
    return failures


def main() -> int:
    repo = DEFAULT_BRAIN_DIR.expanduser().resolve()
    if not repo.exists():
        issue("blocked", [f"repo missing: {repo}"])
        return 0
    if not (repo / ".git").exists():
        issue("blocked", [f"not a git repo: {repo}"])
        return 0

    fetch = git(repo, "fetch", "--prune", REMOTE, BRANCH)
    if fetch.returncode != 0:
        issue(
            "fetch_failed",
            [
                f"repo: {repo}",
                f"remote: {REMOTE}",
                f"branch: {BRANCH}",
                compact(fetch.stdout + fetch.stderr),
            ],
        )
        return 0

    dirty = porcelain(repo)
    if dirty:
        ahead, behind = (0, 0)
        try:
            ahead, behind = upstream_counts(repo)
        except Exception:
            pass
        shown = dirty[:STATUS_LIMIT]
        extra = len(dirty) - len(shown)
        lines = [
            f"repo: {repo}",
            "reason: working tree is dirty; pull skipped",
            f"ahead: {ahead}",
            f"behind: {behind}",
            "dirty files:",
            *[f"- {line}" for line in shown],
        ]
        if extra > 0:
            lines.append(f"... {extra} more")
        issue("blocked", lines)
        return 0

    try:
        ahead, behind = upstream_counts(repo)
    except Exception as exc:
        issue("blocked", [f"repo: {repo}", f"reason: {exc}"])
        return 0

    if ahead > 0 and behind > 0:
        issue(
            "blocked",
            [
                f"repo: {repo}",
                "reason: branch has diverged; manual merge required",
                f"ahead: {ahead}",
                f"behind: {behind}",
            ],
        )
        return 0
    if ahead > 0:
        issue(
            "needs_push",
            [
                f"repo: {repo}",
                "reason: local commits are ahead of upstream; pull skipped",
                f"ahead: {ahead}",
                f"behind: {behind}",
            ],
        )
        return 0
    if behind == 0:
        mark_ok()
        return 0

    pull = git(repo, "pull", "--ff-only", REMOTE, BRANCH)
    if pull.returncode != 0:
        issue(
            "pull_failed",
            [
                f"repo: {repo}",
                f"ahead: {ahead}",
                f"behind: {behind}",
                compact(pull.stdout + pull.stderr),
            ],
        )
        return 0

    failures = validate(repo)
    if failures:
        issue(
            "validation_failed",
            [
                f"repo: {repo}",
                "pull: completed",
                *failures,
            ],
        )
        return 0

    mark_ok()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
