#!/usr/bin/env python3
"""Refresh and narrowly publish the generated iOS capture review queue."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


MANAGED_PATH = "operations/capture-review-queue.md"


def run(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True)


def git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return run(["git", *args], repo)


def compact(result: subprocess.CompletedProcess[str], limit: int = 1200) -> str:
    text = (result.stdout + result.stderr).strip()
    return text if len(text) <= limit else text[: limit - 16].rstrip() + " …[truncated]"


def status_path(line: str) -> str:
    path = line[3:] if len(line) > 3 else ""
    if " -> " in path:
        path = path.split(" -> ", 1)[-1]
    return path.strip().strip('"')


def report(status: str, *lines: str) -> int:
    print("\n".join(("[capture review queue sync]", f"status: {status}", *lines)))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vault", type=Path, default=Path(os.environ.get("SECOND_BRAIN_DIR", "/home/yk/brain-linux")))
    parser.add_argument("--remote", default=os.environ.get("SECOND_BRAIN_REMOTE", "origin"))
    parser.add_argument("--branch", default=os.environ.get("SECOND_BRAIN_BRANCH", "main"))
    parser.add_argument("--no-push", action="store_true")
    args = parser.parse_args(argv)

    repo = args.vault.expanduser().resolve()
    if not (repo / ".git").exists():
        return report("blocked", f"reason: not a git repo: {repo}")

    status = git(repo, "status", "--porcelain")
    if status.returncode != 0:
        return report("blocked", f"reason: git status failed: {compact(status)}")
    dirty = [line for line in status.stdout.splitlines() if line.strip()]
    outside = [line for line in dirty if status_path(line) != MANAGED_PATH]
    if outside:
        return report("blocked_unmanaged_dirty", *[f"- {line}" for line in outside[:20]])
    if dirty:
        return report("blocked_managed_dirty", "reason: previous queue update is still uncommitted")

    fetch = git(repo, "fetch", "--prune", args.remote, args.branch)
    if fetch.returncode != 0:
        return report("fetch_failed", compact(fetch))
    counts = git(repo, "rev-list", "--left-right", "--count", f"HEAD...{args.remote}/{args.branch}")
    if counts.returncode != 0:
        return report("blocked", f"reason: upstream count failed: {compact(counts)}")
    ahead, behind = (int(value) for value in counts.stdout.split()[:2])
    if ahead and behind:
        return report("blocked_diverged", f"ahead: {ahead}", f"behind: {behind}")
    if behind:
        pull = git(repo, "pull", "--ff-only", args.remote, args.branch)
        if pull.returncode != 0:
            return report("pull_failed", compact(pull))

    generator = repo / "operations" / "tools" / "build_capture_review_queue.py"
    generated = run([sys.executable, str(generator), "--vault", str(repo)], repo)
    if generated.returncode != 0:
        return report("generation_failed", compact(generated))
    changed = git(repo, "diff", "--name-only", "--", MANAGED_PATH)
    if changed.returncode != 0:
        return report("diff_failed", compact(changed))
    if not changed.stdout.strip():
        return report("no_changes", generated.stdout.strip())

    lint = run([sys.executable, "operations/tools/brain_lint.py"], repo)
    if lint.returncode != 0:
        return report("lint_failed", compact(lint))
    add = git(repo, "add", "--", MANAGED_PATH)
    if add.returncode != 0:
        return report("add_failed", compact(add))
    check = git(repo, "diff", "--cached", "--check", "--", MANAGED_PATH)
    if check.returncode != 0:
        return report("diff_check_failed", compact(check))
    if args.no_push:
        git(repo, "restore", "--staged", "--", MANAGED_PATH)
        return report("ready_no_push", generated.stdout.strip())

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    commit = git(repo, "commit", "-m", f"docs(capture): refresh review queue {stamp}", "--", MANAGED_PATH)
    if commit.returncode != 0:
        return report("commit_failed", compact(commit))
    push = git(repo, "push", args.remote, f"HEAD:{args.branch}")
    if push.returncode != 0:
        return report("push_failed", compact(push))
    head = git(repo, "rev-parse", "HEAD").stdout.strip()
    return report("pushed", f"commit: {head}", f"file: {MANAGED_PATH}")


if __name__ == "__main__":
    raise SystemExit(main())
