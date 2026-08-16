#!/usr/bin/env python3
"""Render the next general-knowledge promotion request for Hermes."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Hermes executes its pre-run hook from ``~/.hermes/scripts``.  Prefer the
# service runtime directory for shared imports so a stale helper copied next to
# the hook cannot silently parse promotion requests with an older schema.
RUNTIME_DIR = Path.home() / ".local/lib/second-brain-reflection"
if RUNTIME_DIR.is_dir():
    sys.path.insert(0, str(RUNTIME_DIR))

try:
    from render_candidate_promotion_preview_context import (  # type: ignore
        DEFAULT_REPO_URL,
        load_promotion_context,
    )
except ModuleNotFoundError:
    from operations.tools.render_candidate_promotion_preview_context import (
        DEFAULT_REPO_URL,
        load_promotion_context,
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--state",
        type=Path,
        default=Path.home() / ".local/state/second-brain/knowledge-promotion-approval.json",
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
