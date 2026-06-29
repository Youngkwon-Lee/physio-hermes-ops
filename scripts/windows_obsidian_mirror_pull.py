#!/usr/bin/env python3
"""Safely fast-forward the Windows Obsidian second-brain mirror.

This script never merges, commits, stashes, or overwrites local edits. It only
pulls when the mirror is clean, not ahead, and strictly behind origin/main.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path


MIRROR_DIR = Path(os.environ.get("WINDOWS_OBSIDIAN_BRAIN_DIR", "/mnt/c/Users/82106/Documents/brain"))
REMOTE = os.environ.get("WINDOWS_OBSIDIAN_BRAIN_REMOTE", "origin")
BRANCH = os.environ.get("WINDOWS_OBSIDIAN_BRAIN_BRANCH", "main")


def run(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True)


def compact(text: str, limit: int = 1200) -> str:
    text = "\n".join(line.rstrip() for line in text.strip().splitlines())
    if len(text) <= limit:
        return text
    return text[: limit - 32].rstrip() + "\n... [truncated]"


def git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return run(["git", *args], cwd=repo)


def main() -> int:
    repo = MIRROR_DIR.expanduser().resolve()
    if not repo.exists():
        print(f"[windows obsidian mirror]\nstatus: blocked\nreason: repo missing\nrepo: {repo}")
        return 0
    if not (repo / ".git").exists():
        print(f"[windows obsidian mirror]\nstatus: blocked\nreason: not a git repo\nrepo: {repo}")
        return 0

    git(repo, "config", "core.filemode", "false")

    fetch = git(repo, "fetch", "--prune", REMOTE, BRANCH)
    if fetch.returncode != 0:
        print(
            "[windows obsidian mirror]\n"
            "status: fetch_failed\n"
            f"repo: {repo}\n"
            f"remote: {REMOTE}\n"
            f"branch: {BRANCH}\n"
            f"{compact(fetch.stdout + fetch.stderr)}"
        )
        return 0

    dirty = git(repo, "status", "--porcelain")
    if dirty.returncode != 0:
        print(f"[windows obsidian mirror]\nstatus: blocked\nreason: status failed\n{compact(dirty.stdout + dirty.stderr)}")
        return 0
    dirty_lines = [line for line in dirty.stdout.splitlines() if line.strip()]
    if dirty_lines:
        shown = "\n".join(f"- {line}" for line in dirty_lines[:30])
        extra = len(dirty_lines) - 30
        if extra > 0:
            shown += f"\n... {extra} more"
        print(
            "[windows obsidian mirror]\n"
            "status: blocked\n"
            "reason: mirror has local edits; pull skipped\n"
            f"repo: {repo}\n"
            f"dirty files:\n{shown}"
        )
        return 0

    counts = git(repo, "rev-list", "--left-right", "--count", "HEAD...@{upstream}")
    if counts.returncode != 0:
        print(f"[windows obsidian mirror]\nstatus: blocked\nreason: upstream count failed\n{compact(counts.stdout + counts.stderr)}")
        return 0
    ahead_text, behind_text = counts.stdout.strip().split()[:2]
    ahead = int(ahead_text)
    behind = int(behind_text)

    if ahead > 0 and behind > 0:
        print(f"[windows obsidian mirror]\nstatus: blocked\nreason: diverged\nrepo: {repo}\nahead: {ahead}\nbehind: {behind}")
        return 0
    if ahead > 0:
        print(f"[windows obsidian mirror]\nstatus: needs_push\nrepo: {repo}\nahead: {ahead}\nbehind: {behind}")
        return 0
    if behind == 0:
        return 0

    pull = git(repo, "pull", "--ff-only", REMOTE, BRANCH)
    if pull.returncode != 0:
        print(f"[windows obsidian mirror]\nstatus: pull_failed\nrepo: {repo}\n{compact(pull.stdout + pull.stderr)}")
        return 0

    head = git(repo, "rev-parse", "--short", "HEAD").stdout.strip()
    print(f"[windows obsidian mirror]\nstatus: pulled\nrepo: {repo}\nbehind_before: {behind}\nhead: {head}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
