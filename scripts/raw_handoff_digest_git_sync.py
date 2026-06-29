#!/usr/bin/env python3
"""Commit and push raw handoff digests from the canonical second-brain checkout."""

from __future__ import annotations

import os
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path


SOURCE_BRAIN = Path(os.environ.get("SECOND_BRAIN_DIR", "/home/yk/brain-linux"))
SOURCE_DIGESTS = SOURCE_BRAIN / "operations" / "raw-handoff-digests"
REMOTE = os.environ.get("SECOND_BRAIN_REMOTE", "origin")
BRANCH = os.environ.get("SECOND_BRAIN_BRANCH", "main")
GIT_USER_NAME = "Youngkwon-Lee"
GIT_USER_EMAIL = "kwon3856@naver.com"
KST = timezone(timedelta(hours=9))


def run(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, text=True, capture_output=True)


def compact(text: str, limit: int = 1200) -> str:
    text = "\n".join(line.rstrip() for line in text.strip().splitlines())
    if len(text) <= limit:
        return text
    return text[: limit - 32].rstrip() + "\n... [truncated]"


def report(status: str, lines: list[str]) -> None:
    print("\n".join(["[raw handoff digest git sync]", f"status: {status}", *lines]))


def main() -> int:
    stamp = datetime.now(KST).date().isoformat()
    repo = SOURCE_BRAIN.expanduser().resolve()
    digest_dir = SOURCE_DIGESTS

    if not (repo / ".git").exists():
        report("blocked", [f"date: {stamp}", f"reason: not a git repo", f"repo: {repo}"])
        return 0
    if not digest_dir.exists():
        report("source_missing", [f"date: {stamp}", f"source: {digest_dir}"])
        return 0

    source_files = sorted(digest_dir.glob("*.md"))
    if not source_files:
        report("no_digest_files", [f"date: {stamp}", f"source: {digest_dir}"])
        return 0

    run(["git", "config", "user.name", GIT_USER_NAME], cwd=repo)
    run(["git", "config", "user.email", GIT_USER_EMAIL], cwd=repo)
    run(["git", "config", "core.filemode", "true"], cwd=repo)

    fetch = run(["git", "fetch", "--prune", REMOTE, BRANCH], cwd=repo)
    if fetch.returncode != 0:
        report("fetch_failed", [f"date: {stamp}", compact(fetch.stdout + fetch.stderr)])
        return 0

    paths = [str(path.relative_to(repo)) for path in source_files]
    add = run(["git", "add", "--", *paths], cwd=repo)
    if add.returncode != 0:
        report("add_failed", [f"date: {stamp}", compact(add.stdout + add.stderr)])
        return 0

    diff = run(["git", "diff", "--cached", "--name-only", "--", *paths], cwd=repo)
    if diff.returncode != 0:
        report("diff_failed", [f"date: {stamp}", compact(diff.stdout + diff.stderr)])
        return 0
    changed = [line for line in diff.stdout.splitlines() if line.strip()]
    if not changed:
        report("no_changes", [f"date: {stamp}", f"source_files: {len(source_files)}"])
        return 0

    commit = run(["git", "commit", "-m", f"docs(handoff): sync raw handoff digests {stamp}"], cwd=repo)
    if commit.returncode != 0:
        report("commit_failed", [f"date: {stamp}", compact(commit.stdout + commit.stderr)])
        return 0

    push = run(["git", "push", REMOTE, BRANCH], cwd=repo)
    if push.returncode != 0:
        report("push_failed", [f"date: {stamp}", compact(push.stdout + push.stderr)])
        return 0

    head = run(["git", "rev-parse", "--short", "HEAD"], cwd=repo).stdout.strip()
    preview = ", ".join(changed[:20])
    if len(changed) > 20:
        preview += f", ... +{len(changed) - 20} more"
    report(
        "pushed",
        [
            f"date: {stamp}",
            f"source_files: {len(source_files)}",
            f"changed_files: {len(changed)}",
            f"files: {preview}",
            f"commit: {head}",
            f"remote: {REMOTE}/{BRANCH}",
        ],
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
