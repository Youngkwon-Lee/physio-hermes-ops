#!/usr/bin/env python3
"""Commit and push raw handoff digests from the canonical second-brain checkout.

The home desktop has two second-brain checkouts:

- `/home/yk/brain-linux`: automation canonical checkout
- `/mnt/c/Users/82106/Documents/brain`: Windows/Obsidian mirror

Older jobs sometimes wrote raw handoff digests into the mirror. This script
absorbs those mirror-only raw digest files into the canonical checkout before
committing, then removes the mirror copy only after the content is preserved in
the pushed canonical commit.
"""

from __future__ import annotations

import os
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path


SOURCE_BRAIN = Path(os.environ.get("SECOND_BRAIN_DIR", "/home/yk/brain-linux"))
SOURCE_DIGESTS = SOURCE_BRAIN / "operations" / "raw-handoff-digests"
MIRROR_BRAIN = Path(os.environ.get("WINDOWS_OBSIDIAN_BRAIN_DIR", "/mnt/c/Users/82106/Documents/brain"))
MIRROR_DIGESTS = MIRROR_BRAIN / "operations" / "raw-handoff-digests"
REMOTE = os.environ.get("SECOND_BRAIN_REMOTE", "origin")
BRANCH = os.environ.get("SECOND_BRAIN_BRANCH", "main")
GIT_USER_NAME = "Youngkwon-Lee"
GIT_USER_EMAIL = "[redacted-email]"
KST = timezone(timedelta(hours=9))
MANAGED_PREFIX = "operations/raw-handoff-digests/"


def run(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, text=True, capture_output=True)


def compact(text: str, limit: int = 1200) -> str:
    text = "\n".join(line.rstrip() for line in text.strip().splitlines())
    if len(text) <= limit:
        return text
    return text[: limit - 32].rstrip() + "\n... [truncated]"


def report(status: str, lines: list[str]) -> None:
    print("\n".join(["[raw handoff digest git sync]", f"status: {status}", *lines]))


def git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return run(["git", *args], cwd=repo)


def porcelain(repo: Path) -> list[str]:
    result = git(repo, "status", "--porcelain")
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout).strip() or "git status failed")
    return [line for line in result.stdout.splitlines() if line.strip()]


def status_path(line: str) -> str:
    return line[3:].strip().strip('"')


def unmanaged_dirty(repo: Path) -> list[str]:
    lines = porcelain(repo)
    unmanaged = []
    for line in lines:
        path = status_path(line)
        if " -> " in path:
            path = path.split(" -> ", 1)[-1]
        if not path.startswith(MANAGED_PREFIX):
            unmanaged.append(line)
    return unmanaged


def upstream_counts(repo: Path) -> tuple[int, int]:
    result = git(repo, "rev-list", "--left-right", "--count", "HEAD...@{upstream}")
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout).strip() or "upstream not configured")
    ahead_text, behind_text = result.stdout.strip().split()[:2]
    return int(ahead_text), int(behind_text)


def is_tracked(repo: Path, rel_path: str) -> bool:
    result = git(repo, "ls-files", "--error-unmatch", "--", rel_path)
    return result.returncode == 0


def unique_import_target(digest_dir: Path, source_name: str, payload: bytes) -> Path:
    source_path = digest_dir / source_name
    if not source_path.exists() or source_path.read_bytes() == payload:
        return source_path

    stem = source_path.stem
    suffix = source_path.suffix
    for index in range(1, 1000):
        marker = "windows-mirror" if index == 1 else f"windows-mirror-{index}"
        candidate = digest_dir / f"{stem}-{marker}{suffix}"
        if not candidate.exists() or candidate.read_bytes() == payload:
            return candidate
    raise RuntimeError(f"could not allocate mirror import target for {source_name}")


def absorb_mirror_digests(repo: Path) -> dict[Path, Path]:
    """Copy untracked mirror raw digests into the canonical checkout.

    Returns a mapping of mirror source file -> canonical preserved file.
    """

    preserved: dict[Path, Path] = {}
    mirror = MIRROR_BRAIN.expanduser().resolve()
    mirror_digest_dir = MIRROR_DIGESTS.expanduser().resolve()
    canonical_digest_dir = SOURCE_DIGESTS.expanduser().resolve()
    if not (mirror / ".git").exists() or not mirror_digest_dir.exists():
        return preserved

    canonical_digest_dir.mkdir(parents=True, exist_ok=True)
    for mirror_file in sorted(mirror_digest_dir.glob("*.md")):
        rel = mirror_file.relative_to(mirror).as_posix()
        if is_tracked(mirror, rel):
            continue
        payload = mirror_file.read_bytes()
        target = unique_import_target(canonical_digest_dir, mirror_file.name, payload)
        if not target.exists():
            target.write_bytes(payload)
        preserved[mirror_file] = target
    return preserved


def remove_preserved_mirror_files(repo: Path, preserved: dict[Path, Path]) -> list[str]:
    removed: list[str] = []
    for mirror_file, target in preserved.items():
        rel = target.relative_to(repo).as_posix()
        show = git(repo, "show", f"HEAD:{rel}")
        if show.returncode != 0:
            continue
        if show.stdout.encode("utf-8") != target.read_bytes():
            continue
        if mirror_file.exists() and mirror_file.read_bytes() == target.read_bytes():
            mirror_file.unlink()
            removed.append(str(mirror_file))
    return removed


def main() -> int:
    stamp = datetime.now(KST).date().isoformat()
    repo = SOURCE_BRAIN.expanduser().resolve()
    digest_dir = SOURCE_DIGESTS.expanduser().resolve()

    if not (repo / ".git").exists():
        report("blocked", [f"date: {stamp}", f"reason: not a git repo", f"repo: {repo}"])
        return 0
    digest_dir.mkdir(parents=True, exist_ok=True)

    run(["git", "config", "user.name", GIT_USER_NAME], cwd=repo)
    run(["git", "config", "user.email", GIT_USER_EMAIL], cwd=repo)
    run(["git", "config", "core.filemode", "true"], cwd=repo)

    fetch = git(repo, "fetch", "--prune", REMOTE, BRANCH)
    if fetch.returncode != 0:
        report("fetch_failed", [f"date: {stamp}", compact(fetch.stdout + fetch.stderr)])
        return 0

    dirty_outside = unmanaged_dirty(repo)
    if dirty_outside:
        report(
            "blocked_unmanaged_dirty",
            [
                f"date: {stamp}",
                f"repo: {repo}",
                "reason: refusing to mix raw digest sync with unrelated changes",
                "dirty files:",
                *[f"- {line}" for line in dirty_outside[:30]],
            ],
        )
        return 0

    try:
        ahead, behind = upstream_counts(repo)
    except Exception as exc:
        report("blocked", [f"date: {stamp}", f"repo: {repo}", f"reason: {exc}"])
        return 0

    if ahead > 0 and behind > 0:
        report(
            "blocked_diverged",
            [
                f"date: {stamp}",
                f"repo: {repo}",
                "reason: local branch diverged; manual rebase required",
                f"ahead: {ahead}",
                f"behind: {behind}",
            ],
        )
        return 0

    if ahead == 0 and behind > 0:
        pull = git(repo, "pull", "--ff-only", REMOTE, BRANCH)
        if pull.returncode != 0:
            report(
                "pull_failed",
                [
                    f"date: {stamp}",
                    f"repo: {repo}",
                    f"behind: {behind}",
                    compact(pull.stdout + pull.stderr),
                ],
            )
            return 0

    preserved = absorb_mirror_digests(repo)
    source_files = sorted(digest_dir.glob("*.md"))
    if not source_files:
        report(
            "no_digest_files",
            [
                f"date: {stamp}",
                f"source: {digest_dir}",
                f"mirror_imported: {len(preserved)}",
            ],
        )
        return 0

    paths = [str(path.relative_to(repo)) for path in source_files]
    add = git(repo, "add", "--", *paths)
    if add.returncode != 0:
        report("add_failed", [f"date: {stamp}", compact(add.stdout + add.stderr)])
        return 0

    diff = git(repo, "diff", "--cached", "--name-only", "--", *paths)
    if diff.returncode != 0:
        report("diff_failed", [f"date: {stamp}", compact(diff.stdout + diff.stderr)])
        return 0
    changed = [line for line in diff.stdout.splitlines() if line.strip()]
    if not changed:
        removed = remove_preserved_mirror_files(repo, preserved)
        report(
            "no_changes",
            [
                f"date: {stamp}",
                f"source_files: {len(source_files)}",
                f"mirror_imported: {len(preserved)}",
                f"mirror_cleaned: {len(removed)}",
            ],
        )
        return 0

    commit = git(repo, "commit", "-m", f"docs(handoff): sync raw handoff digests {stamp}")
    if commit.returncode != 0:
        report("commit_failed", [f"date: {stamp}", compact(commit.stdout + commit.stderr)])
        return 0

    push = git(repo, "push", REMOTE, BRANCH)
    if push.returncode != 0:
        report("push_failed", [f"date: {stamp}", compact(push.stdout + push.stderr)])
        return 0

    removed = remove_preserved_mirror_files(repo, preserved)
    head = git(repo, "rev-parse", "--short", "HEAD").stdout.strip()
    preview = ", ".join(changed[:20])
    if len(changed) > 20:
        preview += f", ... +{len(changed) - 20} more"
    report(
        "pushed",
        [
            f"date: {stamp}",
            f"source_files: {len(source_files)}",
            f"changed_files: {len(changed)}",
            f"mirror_imported: {len(preserved)}",
            f"mirror_cleaned: {len(removed)}",
            f"files: {preview}",
            f"commit: {head}",
            f"remote: {REMOTE}/{BRANCH}",
        ],
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
