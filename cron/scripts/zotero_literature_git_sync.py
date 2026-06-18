#!/usr/bin/env python3
"""Sync Zotero literature notes from desktop brain to GitHub.

This follows the existing Notion candidate sync pattern: use a clean temporary
clone, copy only the bounded target files, then commit/push if there is a diff.
It avoids committing unrelated dirty files from /home/yk/brain.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path


SOURCE_BRAIN = Path("/home/yk/brain")
SOURCE_LITERATURE = SOURCE_BRAIN / "research" / "literature"
REPO_URL = "git@github.com:Youngkwon-Lee/second-brain.git"
BRANCH = "main"
GIT_USER_NAME = "Youngkwon-Lee"
GIT_USER_EMAIL = "kwon3856@naver.com"
KST = timezone(timedelta(hours=9))


def run(args: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, text=True, capture_output=True, check=True)


def copy_tree_files(source_dir: Path, target_dir: Path) -> list[str]:
    copied: list[str] = []
    for source in sorted(source_dir.glob("*.md")):
        target = target_dir / source.name
        shutil.copy2(source, target)
        copied.append(str(target.relative_to(target_dir.parents[1])))
    return copied


def main() -> int:
    stamp = datetime.now(KST).date().isoformat()
    if not SOURCE_LITERATURE.exists():
        print(
            "[zotero literature git sync]\n"
            f"date: {stamp}\n"
            "status: source missing\n"
            f"source: {SOURCE_LITERATURE}"
        )
        return 0

    source_files = sorted(SOURCE_LITERATURE.glob("*.md"))
    if not source_files:
        print(
            "[zotero literature git sync]\n"
            f"date: {stamp}\n"
            "status: no literature files"
        )
        return 0

    with tempfile.TemporaryDirectory(prefix="brain-zotero-sync-") as tmp:
        tmpdir = Path(tmp)
        repo_dir = tmpdir / "repo"
        run(["git", "clone", "--branch", BRANCH, REPO_URL, str(repo_dir)])
        run(["git", "config", "user.name", GIT_USER_NAME], cwd=repo_dir)
        run(["git", "config", "user.email", GIT_USER_EMAIL], cwd=repo_dir)

        literature_dir = repo_dir / "research" / "literature"
        literature_dir.mkdir(parents=True, exist_ok=True)
        copied = copy_tree_files(SOURCE_LITERATURE, literature_dir)

        run(["git", "add", "--", *copied], cwd=repo_dir)
        diff = run(["git", "diff", "--cached", "--name-only", "--", *copied], cwd=repo_dir)
        changed = [line for line in diff.stdout.splitlines() if line.strip()]
        if not changed:
            print(
                "[zotero literature git sync]\n"
                f"date: {stamp}\n"
                "status: no changes\n"
                f"source_files: {len(source_files)}"
            )
            return 0

        message = f"docs(literature): sync zotero notes {stamp}"
        run(["git", "commit", "-m", message], cwd=repo_dir)
        run(["git", "push", "origin", BRANCH], cwd=repo_dir)
        head = run(["git", "rev-parse", "HEAD"], cwd=repo_dir).stdout.strip()
        preview = ", ".join(changed[:20])
        if len(changed) > 20:
            preview += f", ... +{len(changed) - 20} more"
        print(
            "[zotero literature git sync]\n"
            f"date: {stamp}\n"
            "status: pushed\n"
            f"source_files: {len(source_files)}\n"
            f"changed_files: {len(changed)}\n"
            f"files: {preview}\n"
            f"commit: {head}\n"
            f"remote: origin/{BRANCH}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
