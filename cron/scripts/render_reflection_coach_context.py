#!/usr/bin/env python3
"""Render privacy-safe count-only context for the nightly reflection coach."""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from typing import Any

try:
    from .render_reflection_nudge import (
        DEFAULT_PACKET_PATH,
        KST,
        REFLECTION_THREAD_ID,
        count_value,
    )
except ImportError:  # direct script execution
    from render_reflection_nudge import (
        DEFAULT_PACKET_PATH,
        KST,
        REFLECTION_THREAD_ID,
        count_value,
    )


JOURNAL_ACTIONS = {
    "approved-interpretation-present",
    "ask-user-before-journal",
    "no-journal-needed",
    "review-existing-draft",
}


def render_coach_context(packet: dict[str, Any], anchor: dt.date) -> str | None:
    if packet.get("schema") != "reflection-packet-v1":
        return None
    if packet.get("period") != "daily" or packet.get("label") != anchor.isoformat():
        return None
    journal_action = packet.get("journal_action")
    if journal_action not in JOURNAL_ACTIONS:
        return None

    counts = packet.get("counts")
    if not isinstance(counts, dict):
        return None
    values = {
        key: count_value(counts, key)
        for key in ("intention", "execution", "reality", "interpretation", "ai_log")
    }
    if any(value is None for value in values.values()):
        return None

    alignment = packet.get("plan_alignment") or {}
    alignment_values = {
        key: count_value(alignment, key)
        for key in ("total", "confirmed", "weak", "none")
    }
    alignment_line = None
    if all(value is not None for value in alignment_values.values()):
        if alignment_values["total"] != sum(
            alignment_values[key] for key in ("confirmed", "weak", "none")
        ):
            return None
        alignment_line = (
            "- plan_evidence_signal: "
            f"total={alignment_values['total']}, confirmed={alignment_values['confirmed']}, "
            f"weak={alignment_values['weak']}, none={alignment_values['none']}"
        )

    lines = [
            "[reflection-coach-context-v1]",
            f"- date: {anchor.isoformat()}",
            f"- target_thread_id: {REFLECTION_THREAD_ID}",
            (
                "- signal_counts: "
                f"intention={values['intention']}, execution={values['execution']}, "
                f"reality={values['reality']}, interpretation={values['interpretation']}, "
                f"ai_log={values['ai_log']}"
            ),
            f"- journal_action: {journal_action}",
            "- privacy_contract: counts-only; no note titles, paths, or raw content",
        ]
    if alignment_line:
        lines.insert(-1, alignment_line)
    return "\n".join(lines)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_PACKET_PATH)
    parser.add_argument("--date", type=dt.date.fromisoformat)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    anchor = args.date or dt.datetime.now(KST).date()
    try:
        packet = json.loads(args.input.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return 0
    if not isinstance(packet, dict):
        return 0
    rendered = render_coach_context(packet, anchor)
    if rendered:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
