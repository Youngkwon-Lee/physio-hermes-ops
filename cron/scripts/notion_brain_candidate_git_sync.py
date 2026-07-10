#!/usr/bin/env python3
from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

HELPER_ROOT = Path("/home/yk/physio-hermes-ops/cron/scripts")
if str(HELPER_ROOT) not in sys.path:
    sys.path.insert(0, str(HELPER_ROOT))

from git_sync_helpers import restore_stash, stash_paths, status_path, unique_dirty_paths

SOURCE_BRAIN = Path(os.environ.get("SECOND_BRAIN_DIR", "/home/yk/brain-linux"))
SOURCE_CANDIDATES = SOURCE_BRAIN / "candidates"
REMOTE = os.environ.get("SECOND_BRAIN_REMOTE", "origin")
BRANCH = os.environ.get("SECOND_BRAIN_BRANCH", "main")
GIT_USER_NAME = "Youngkwon-Lee"
GIT_USER_EMAIL = "[redacted-email]"
KST = timezone(timedelta(hours=9))


def run(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, text=True, capture_output=True)


def compact(text: str, limit: int = 1200) -> str:
    text = "\n".join(line.rstrip() for line in text.strip().splitlines())
    if len(text) <= limit:
        return text
    return text[: limit - 32].rstrip() + "\n... [truncated]"


def report(status: str, lines: list[str]) -> None:
    print("\n".join(["[second-brain candidate sync]", f"status: {status}", *lines]))


def git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return run(["git", *args], cwd=repo)


def dirty_outside(repo: Path, managed: set[str]) -> list[str]:
    result = git(repo, "status", "--porcelain")
    if result.returncode != 0:
        return [compact(result.stdout + result.stderr)]
    unmanaged: list[str] = []
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        path = status_path(line)
        if " -> " in path:
            path = path.split(" -> ", 1)[-1]
        if path not in managed:
            unmanaged.append(line)
    return unmanaged


def clear_remote_duplicate_untracked(repo: Path, rel_files: list[str]) -> list[str]:
    cleared: list[str] = []
    for rel in rel_files:
        path = repo / rel
        if not path.exists():
            continue
        tracked = git(repo, "ls-files", "--error-unmatch", "--", rel)
        if tracked.returncode == 0:
            continue
        remote = git(repo, "show", f"{REMOTE}/{BRANCH}:{rel}")
        if remote.returncode != 0:
            continue
        if remote.stdout.encode("utf-8") == path.read_bytes():
            path.unlink()
            cleared.append(rel)
    return cleared


def upstream_counts(repo: Path) -> tuple[int, int]:
    result = git(repo, "rev-list", "--left-right", "--count", "HEAD...@{upstream}")
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout).strip() or "upstream not configured")
    ahead_text, behind_text = result.stdout.strip().split()[:2]
    return int(ahead_text), int(behind_text)


def main() -> int:
    stamp = datetime.now(KST).date().isoformat()
    repo = SOURCE_BRAIN.expanduser().resolve()
    if not (repo / ".git").exists():
        report("blocked", [f"date: {stamp}", f"reason: not a git repo", f"repo: {repo}"])
        return 0

    target_names = [
        f"notion-ai-news-weekly-{stamp}.md",
        f"notion-rehab-research-weekly-{stamp}.md",
        f"notion-biz-support-radar-weekly-{stamp}.md",
        f"ai-news-brief-{stamp}.md",
        f"rehab-ai-brief-{stamp}.md",
        f"external-opportunity-brief-{stamp}.md",
    ]
    rel_files = [f"candidates/{name}" for name in target_names if (SOURCE_CANDIDATES / name).exists()]
    if not rel_files:
        report("no_candidate_files", [f"date: {stamp}", f"source: {SOURCE_CANDIDATES}"])
        return 0

    run(["git", "config", "user.name", GIT_USER_NAME], cwd=repo)
    run(["git", "config", "user.email", GIT_USER_EMAIL], cwd=repo)
    run(["git", "config", "core.filemode", "true"], cwd=repo)

    fetch = git(repo, "fetch", "--prune", REMOTE, BRANCH)
    if fetch.returncode != 0:
        report("fetch_failed", [f"date: {stamp}", compact(fetch.stdout + fetch.stderr)])
        return 0

    try:
        ahead, behind = upstream_counts(repo)
    except Exception as exc:
        report("blocked", [f"date: {stamp}", f"repo: {repo}", f"reason: {exc}"])
        return 0

    outside = dirty_outside(repo, set(rel_files))
    stash_ref: str | None = None
    stashed_paths: list[str] = []

    if outside and behind == 0:
        report(
            "blocked_unmanaged_dirty",
            [
                f"date: {stamp}",
                f"repo: {repo}",
                "reason: refusing to mix candidate sync with unrelated changes",
                "dirty files:",
                *[f"- {line}" for line in outside[:30]],
            ],
        )
        return 0

    cleared_duplicates: list[str] = []
    if behind > 0:
        stashed_paths = unique_dirty_paths(outside)
        if stashed_paths:
            stash_ref, stash_error = stash_paths(repo, stashed_paths, f"temp-before-candidate-sync-{stamp}", git, compact)
            if stash_error:
                report(
                    "stash_failed",
                    [
                        f"date: {stamp}",
                        f"repo: {repo}",
                        "reason: failed to stash unrelated dirty paths before pull",
                        f"paths: {', '.join(stashed_paths)}",
                        stash_error,
                    ],
                )
                return 0

        cleared_duplicates = clear_remote_duplicate_untracked(repo, rel_files)
        outside_after_clear = dirty_outside(repo, set(rel_files))
        if outside_after_clear:
            restore_error = restore_stash(repo, stash_ref, git, compact)
            lines = [
                f"date: {stamp}",
                f"repo: {repo}",
                "reason: unrelated changes remain before pull",
                "dirty files:",
                *[f"- {line}" for line in outside_after_clear[:30]],
            ]
            if restore_error:
                lines.append(f"stash_restore_error: {restore_error}")
            report("blocked_unmanaged_dirty", lines)
            return 0

        sync = git(repo, "rebase", f"{REMOTE}/{BRANCH}")
        if sync.returncode != 0:
            abort = git(repo, "rebase", "--abort")
            restore_error = restore_stash(repo, stash_ref, git, compact)
            lines = [
                f"date: {stamp}",
                f"ahead_before_sync: {ahead}",
                f"behind_before_sync: {behind}",
                compact(sync.stdout + sync.stderr),
            ]
            abort_text = compact(abort.stdout + abort.stderr)
            if abort.returncode == 0 and abort_text:
                lines.append(f"rebase_abort: {abort_text}")
            elif abort.returncode != 0:
                lines.append(f"rebase_abort_error: {abort_text}")
            if restore_error:
                lines.append(f"stash_restore_error: {restore_error}")
            report("sync_failed", lines)
            return 0

    for rel in rel_files:
        path = repo / rel
        if path.exists():
            path.chmod(0o644)
    add = git(repo, "add", "--", *rel_files)
    if add.returncode != 0:
        restore_error = restore_stash(repo, stash_ref, git, compact)
        lines = [f"date: {stamp}", compact(add.stdout + add.stderr)]
        if restore_error:
            lines.append(f"stash_restore_error: {restore_error}")
        report("add_failed", lines)
        return 0

    diff = git(repo, "diff", "--cached", "--name-only", "--", *rel_files)
    if diff.returncode != 0:
        restore_error = restore_stash(repo, stash_ref, git, compact)
        lines = [f"date: {stamp}", compact(diff.stdout + diff.stderr)]
        if restore_error:
            lines.append(f"stash_restore_error: {restore_error}")
        report("diff_failed", lines)
        return 0
    changed = [line for line in diff.stdout.splitlines() if line.strip()]
    if not changed:
        restore_error = restore_stash(repo, stash_ref, git, compact)
        lines = [f"date: {stamp}", f"files: {', '.join(rel_files)}"]
        if restore_error:
            lines.append(f"stash_restore_error: {restore_error}")
        report("no_changes", lines)
        return 0

    message = f"docs(candidates): sync notion candidates {stamp}"
    commit = git(repo, "commit", "-m", message)
    if commit.returncode != 0:
        restore_error = restore_stash(repo, stash_ref, git, compact)
        lines = [f"date: {stamp}", compact(commit.stdout + commit.stderr)]
        if restore_error:
            lines.append(f"stash_restore_error: {restore_error}")
        report("commit_failed", lines)
        return 0

    push = git(repo, "push", REMOTE, f"HEAD:{BRANCH}")
    if push.returncode != 0:
        restore_error = restore_stash(repo, stash_ref, git, compact)
        lines = [f"date: {stamp}", compact(push.stdout + push.stderr)]
        if restore_error:
            lines.append(f"stash_restore_error: {restore_error}")
        report("push_failed", lines)
        return 0

    head = git(repo, "rev-parse", "HEAD").stdout.strip()
    restore_error = restore_stash(repo, stash_ref, git, compact)
    lines = [
        f"date: {stamp}",
        f"files: {', '.join(changed)}",
        f"commit: {head}",
        f"remote: {REMOTE}/{BRANCH}",
        f"cleared_remote_duplicates: {len(cleared_duplicates)}",
    ]
    if stashed_paths:
        lines.append(f"stashed_unmanaged_paths: {len(stashed_paths)}")
    if restore_error:
        lines.append(f"stash_restore_error: {restore_error}")
    report("pushed", lines)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
