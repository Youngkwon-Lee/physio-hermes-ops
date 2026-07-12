from __future__ import annotations

from pathlib import Path
from typing import Callable


GitRunner = Callable[[Path, str], object]


def status_path(line: str) -> str:
    path = line[3:] if len(line) > 3 else ""
    if " -> " in path:
        path = path.split(" -> ", 1)[-1]
    return path.strip().strip('"')


def unique_dirty_paths(lines: list[str]) -> list[str]:
    paths: list[str] = []
    seen: set[str] = set()
    for line in lines:
        path = status_path(line)
        if path and path not in seen:
            seen.add(path)
            paths.append(path)
    return paths


def stash_paths(
    repo: Path,
    paths: list[str],
    message: str,
    git: Callable[..., object],
    compact: Callable[[str], str],
) -> tuple[str | None, str | None]:
    if not paths:
        return None, None

    before = git(repo, "stash", "list")
    before_top = before.stdout.splitlines()[0] if getattr(before, "returncode", 1) == 0 and before.stdout.splitlines() else None
    stash = git(repo, "stash", "push", "-u", "-m", message, "--", *paths)
    if getattr(stash, "returncode", 1) != 0:
        return None, compact(stash.stdout + stash.stderr)
    if "No local changes to save" in stash.stdout:
        return None, None

    after = git(repo, "stash", "list")
    if getattr(after, "returncode", 1) != 0:
        return None, compact(after.stdout + after.stderr)
    after_top = after.stdout.splitlines()[0] if after.stdout.splitlines() else None
    if after_top and after_top != before_top:
        return after_top.split(":", 1)[0], None
    return None, None


def restore_stash(
    repo: Path,
    stash_ref: str | None,
    git: Callable[..., object],
    compact: Callable[[str], str],
) -> str | None:
    if not stash_ref:
        return None
    apply = git(repo, "stash", "apply", stash_ref)
    if getattr(apply, "returncode", 1) != 0:
        return compact(apply.stdout + apply.stderr)
    drop = git(repo, "stash", "drop", stash_ref)
    if getattr(drop, "returncode", 1) != 0:
        return compact(drop.stdout + drop.stderr)
    return None
