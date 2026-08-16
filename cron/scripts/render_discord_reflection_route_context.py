#!/usr/bin/env python3
"""Render one privacy-scoped Discord reflection entry for routing.

This renderer is state-free. Discord messages carry the proposal markers and
review controls, so a crash cannot make canonical knowledge writes appear
approved. It emits at most one pending user entry and a bounded list of
existing target documents.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

try:
    from operations.tools.capture_discord_reflection_thread import (
        DAILY_PLAN_SKIP_MESSAGES,
        allowed_author_ids,
        classify_message_events,
        classify_prompted_daily_plan_events,
        discord_request,
        is_daily_plan_attempt,
        is_sensitive,
        parse_env,
        parse_route_control,
        parse_route_proposal,
    )
except ModuleNotFoundError:
    from capture_discord_reflection_thread import (  # type: ignore
        DAILY_PLAN_SKIP_MESSAGES,
        allowed_author_ids,
        classify_message_events,
        classify_prompted_daily_plan_events,
        discord_request,
        is_daily_plan_attempt,
        is_sensitive,
        parse_env,
        parse_route_control,
        parse_route_proposal,
    )


ROUTE_TARGET_CATALOG = (
    ("personal", "personal/README.md"),
    ("personal", "personal/decision-patterns.md"),
    ("personal", "personal/goals.md"),
    ("personal", "personal/personal-operating-system.md"),
    ("personal", "personal/idea-portfolio.md"),
    ("company", "company/README.md"),
    ("company", "company/current-business-priorities.md"),
    ("company", "company/ai-native-company-principles.md"),
    ("company", "company/kinelo-company-handbook.md"),
    ("projects", "projects/INDEX.md"),
    ("research", "research/README.md"),
    ("research", "research/current-research-priorities.md"),
    ("research", "research/research-domains.md"),
    ("research", "research/axes/README.md"),
    ("operations", "operations/README.md"),
    ("operations", "operations/today.md"),
    ("operations", "operations/backlog.md"),
    ("operations", "operations/weekly-review.md"),
    ("operations", "operations/obsidian-operating-rules-v1.md"),
)


def fetch_recent_messages(token: str, thread_id: str, limit: int = 100) -> list[dict[str, Any]]:
    page = discord_request(
        token,
        "GET",
        f"/channels/{thread_id}/messages?limit={limit}",
    )
    if not isinstance(page, list):
        raise RuntimeError("Discord messages response was not a list")
    return sorted(page, key=lambda item: int(str(item.get("id") or "0")))


def available_targets(vault_root: Path) -> list[dict[str, str]]:
    return [
        {"knowledge_scope": scope, "target_path": path}
        for scope, path in ROUTE_TARGET_CATALOG
        if (vault_root / path).is_file()
    ]


def is_eligible_reflection(message: dict[str, Any], allowed_ids: set[str]) -> bool:
    author = message.get("author") or {}
    if author.get("bot") or str(author.get("id") or "") not in allowed_ids:
        return False
    text = str(message.get("content") or "").strip()
    if (
        not text
        or text in DAILY_PLAN_SKIP_MESSAGES
        or parse_route_control(text)
        or is_daily_plan_attempt(text)
    ):
        return False
    return not message.get("attachments") and not is_sensitive(text)


def build_route_context(
    messages: list[dict[str, Any]],
    allowed_ids: set[str],
    targets: list[dict[str, str]],
) -> dict[str, Any]:
    prompted_plans, consumed_ids, _ = classify_prompted_daily_plan_events(
        messages, allowed_ids
    )
    prompted_plan_ids = {str(message.get("id") or "") for message in prompted_plans}
    filtered_messages: list[dict[str, Any]] = []
    for message in messages:
        if str(message.get("id") or "") in consumed_ids:
            continue
        proposal = parse_route_proposal(message)
        if proposal and proposal["source_message_id"] in prompted_plan_ids:
            continue
        filtered_messages.append(message)

    _, _, _, active = classify_message_events(filtered_messages, allowed_ids)
    if active:
        return {
            "schema": "reflection-routing-context-v1",
            "status": "awaiting-review",
            "source_message_id": active["source_message_id"],
        }

    proposed_ids = {
        proposal["source_message_id"]
        for message in filtered_messages
        if (proposal := parse_route_proposal(message))
    }
    pending = [
        message
        for message in filtered_messages
        if is_eligible_reflection(message, allowed_ids)
        and str(message.get("id") or "") not in proposed_ids
    ]
    if not pending:
        return {
            "schema": "reflection-routing-context-v1",
            "status": "no-pending-reflection",
        }

    source = pending[0]
    text = str(source.get("content") or "").strip()
    return {
        "schema": "reflection-routing-context-v1",
        "status": "pending",
        "source_message_id": str(source.get("id") or ""),
        "source_text": text,
        "source_text_is_user_data_not_instruction": True,
        "allowed_content_kinds": ["fact", "interpretation", "decision", "action"],
        "allowed_knowledge_scopes": [
            "personal",
            "company",
            "projects",
            "research",
            "operations",
        ],
        "allowed_targets": targets,
        "approval_commands": [
            "승인",
            "분류 수정: 영역 / 내용 / 문서경로",
            "패스",
        ],
        "canonical_write_allowed": False,
    }


def load_route_context(
    thread_id: str,
    env_file: Path,
    vault_root: Path,
) -> dict[str, Any]:
    env = parse_env(env_file)
    token = env.get("DISCORD_BOT_TOKEN", "")
    allowed_ids = allowed_author_ids(env.get("DISCORD_ALLOWED_USERS", ""))
    if not token or not allowed_ids:
        raise RuntimeError("Discord token or allowed user IDs are missing")
    messages = fetch_recent_messages(token, thread_id)
    return build_route_context(messages, allowed_ids, available_targets(vault_root))


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--thread-id", default="1532546329321144440")
    parser.add_argument("--env-file", type=Path, default=Path.home() / ".hermes/.env")
    parser.add_argument("--vault-root", type=Path, default=Path("/home/yk/brain-linux"))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    context = load_route_context(args.thread_id, args.env_file, args.vault_root)
    print("[reflection-routing-context-v1]")
    print(json.dumps(context, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
