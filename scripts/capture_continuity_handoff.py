#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "continuity_handoff_v0_1"


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def slug(value: str) -> str:
    text = re.sub(r"[^a-zA-Z0-9._-]+", "-", value).strip("-").lower()
    return text[:72] or "handoff"


def read_payload(path: Path | None) -> dict[str, Any]:
    raw = path.read_text(encoding="utf-8") if path else sys.stdin.read()
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("handoff payload must be an object")
    return payload


def resolve_brain_dir(value: str | None) -> Path:
    if value:
        return Path(value).expanduser()
    env_value = os.getenv("SECOND_BRAIN_DIR")
    if env_value:
        return Path(env_value).expanduser()
    home_brain = Path.home() / "brain"
    if home_brain.exists():
        return home_brain
    return ROOT / "ops_knowledge"


def require_list(payload: dict[str, Any], key: str) -> list[str]:
    value = payload.get(key)
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f"{key} must be a list")
    return [str(item).strip() for item in value if str(item).strip()]


def normalize(payload: dict[str, Any]) -> dict[str, Any]:
    if payload.get("schema") != SCHEMA:
        raise ValueError(f"schema must be {SCHEMA}")
    source = payload.get("source")
    if not isinstance(source, dict) or not str(source.get("surface") or "").strip():
        raise ValueError("source.surface is required")
    goal = str(payload.get("goal") or "").strip()
    if not goal:
        raise ValueError("goal is required")

    normalized = {
        "schema": SCHEMA,
        "id": str(payload.get("id") or f"handoff-{uuid.uuid4()}"),
        "createdAt": str(payload.get("createdAt") or now_iso()),
        "source": {key: value for key, value in source.items() if value is not None and str(value).strip()},
        "goal": goal,
        "done": require_list(payload, "done"),
        "next": require_list(payload, "next"),
        "blockers": require_list(payload, "blockers"),
        "decisions": payload.get("decisions") if isinstance(payload.get("decisions"), list) else [],
        "artifacts": payload.get("artifacts") if isinstance(payload.get("artifacts"), list) else [],
        "memoryCandidates": payload.get("memoryCandidates") if isinstance(payload.get("memoryCandidates"), list) else [],
    }
    if not normalized["done"] and not normalized["next"]:
        raise ValueError("at least one done or next item is required")
    return normalized


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def bullet(items: list[str]) -> str:
    if not items:
        return "- none"
    return "\n".join(f"- {item}" for item in items)


def raw_markdown(payload: dict[str, Any], raw_json_path: Path, brain_dir: Path) -> str:
    source = payload["source"]
    return "\n".join(
        [
            f"# Continuity Handoff: {payload['goal']}",
            f"- id: {payload['id']}",
            f"- created_at: {payload['createdAt']}",
            f"- source_surface: {source.get('surface', '-')}",
            f"- run_id: {source.get('runId', '-')}",
            f"- thread_id: {source.get('threadId', '-')}",
            f"- repo: {source.get('repo', '-')}",
            f"- branch: {source.get('branch', '-')}",
            f"- raw_json: {raw_json_path.relative_to(brain_dir)}",
            "",
            "## Goal",
            payload["goal"],
            "",
            "## Done",
            bullet(payload["done"]),
            "",
            "## Next",
            bullet(payload["next"]),
            "",
            "## Blockers",
            bullet(payload["blockers"]),
            "",
        ]
    )


def candidate_markdown(candidate: dict[str, Any], payload: dict[str, Any], raw_md_path: Path, brain_dir: Path) -> str:
    return "\n".join(
        [
            f"# Candidate: {candidate['title']}",
            "- status: pending",
            f"- type: {candidate['type']}",
            f"- source_handoff_id: {payload['id']}",
            f"- source_run_id: {payload['source'].get('runId', '-')}",
            f"- linked_raw: {raw_md_path.relative_to(brain_dir)}",
            f"- proposed_destination: {candidate.get('proposedDestination') or '-'}",
            f"- confidence: {candidate.get('confidence', '-')}",
            "",
            "## Summary",
            str(candidate["summary"]).strip(),
            "",
            "## Why It Matters",
            str(candidate.get("whyItMatters") or "-").strip(),
            "",
            "## Promotion Filter",
            "- [ ] reusable",
            "- [ ] needed for handoff",
            "- [ ] decision provenance",
            "- [ ] failure to avoid",
            "- [ ] shared rule or guide",
            "",
        ]
    )


def valid_candidate(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    title = str(value.get("title") or "").strip()
    candidate_type = str(value.get("type") or "").strip()
    summary = str(value.get("summary") or "").strip()
    if not title or candidate_type not in {"decision", "rule", "failure", "context", "todo"} or not summary:
        return None
    return {
        "title": title,
        "type": candidate_type,
        "summary": summary,
        "whyItMatters": str(value.get("whyItMatters") or "").strip(),
        "proposedDestination": str(value.get("proposedDestination") or "").strip(),
        "confidence": value.get("confidence") if isinstance(value.get("confidence"), (int, float)) else None,
    }


def capture(payload: dict[str, Any], brain_dir: Path, no_candidate: bool) -> dict[str, Any]:
    normalized = normalize(payload)
    stamp = datetime.now().strftime("%H%M%S")
    base_name = f"{stamp}-{slug(normalized['goal'])}"
    raw_dir = brain_dir / "operations" / "raw" / "continuity" / today()
    candidate_dir = brain_dir / "operations" / "candidates" / "continuity" / today()
    raw_json_path = raw_dir / f"{base_name}.json"
    raw_md_path = raw_dir / f"{base_name}.md"

    write_json(raw_json_path, normalized)
    write_text(raw_md_path, raw_markdown(normalized, raw_json_path, brain_dir))

    candidate_paths: list[str] = []
    if not no_candidate:
        for index, raw_candidate in enumerate(normalized["memoryCandidates"], start=1):
            candidate = valid_candidate(raw_candidate)
            if candidate is None:
                continue
            path = candidate_dir / f"{base_name}-{index:02d}-{slug(candidate['title'])}.md"
            write_text(path, candidate_markdown(candidate, normalized, raw_md_path, brain_dir))
            candidate_paths.append(str(path))

    return {
        "ok": True,
        "brainDir": str(brain_dir),
        "handoffId": normalized["id"],
        "rawJsonPath": str(raw_json_path),
        "rawMarkdownPath": str(raw_md_path),
        "candidatePaths": candidate_paths,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Capture a Codex/Hermes continuity handoff.")
    parser.add_argument("--input", type=Path, default=None, help="JSON file. Reads stdin when omitted.")
    parser.add_argument("--brain-dir", default=None, help="second-brain directory. Defaults to SECOND_BRAIN_DIR, ~/brain, then ops_knowledge.")
    parser.add_argument("--no-candidate", action="store_true", help="Write raw only.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        payload = read_payload(args.input)
        result = capture(payload, resolve_brain_dir(args.brain_dir), args.no_candidate)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
