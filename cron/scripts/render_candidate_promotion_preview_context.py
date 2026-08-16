#!/usr/bin/env python3
"""Render one approved candidate route as a bounded promotion preview context."""

from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any

try:
    from operations.tools.candidate_promotion_workflow import build_promotion_context
except ModuleNotFoundError:
    from candidate_promotion_workflow import build_promotion_context  # type: ignore


DEFAULT_REPO_URL = "git@github.com:Youngkwon-Lee/second-brain.git"


def load_state(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def load_promotion_context(
    state_path: Path,
    repo_url: str = DEFAULT_REPO_URL,
    branch: str = "main",
) -> dict[str, Any]:
    state = load_state(state_path)
    queue = state.get("promotion_queue") or []
    if not queue:
        return {"schema": "promotion-preview-context-v1", "status": "no-pending-promotion"}
    request = queue[0]
    with tempfile.TemporaryDirectory(prefix="promotion-preview-context-") as temp:
        repo_dir = Path(temp) / "repo"
        subprocess.run(
            ["git", "clone", "--depth", "1", "--branch", branch, repo_url, str(repo_dir)],
            text=True,
            capture_output=True,
            check=True,
        )
        return build_promotion_context(repo_dir, request)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--state",
        type=Path,
        default=Path.home() / ".local/state/second-brain/discord-reflection-capture.json",
    )
    parser.add_argument("--repo-url", default=DEFAULT_REPO_URL)
    parser.add_argument("--branch", default="main")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    context = load_promotion_context(args.state, args.repo_url, args.branch)
    print("[promotion-preview-context-v1]")
    print(json.dumps(context, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
