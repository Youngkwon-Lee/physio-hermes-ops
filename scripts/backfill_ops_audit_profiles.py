#!/usr/bin/env python3
"""Backfill missing profile_ids in lineage/actions_audit.jsonl.

Heuristic:
1) Use lineage events near audit time (default ±30 minutes).
2) If none, use latest events before audit time within lookback window.
3) If still none, optionally set ['legacy-unknown'] with --use-unknown.

Default is dry-run. Use --apply to write changes.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
AUDIT_PATH = ROOT / "lineage" / "actions_audit.jsonl"
EVENTS_PATH = ROOT / "lineage" / "events.jsonl"


def parse_ts(v: str | None) -> datetime | None:
    if not v:
        return None
    s = str(v).strip()
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if dt.tzinfo is not None:
            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt
    except Exception:
        return None


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            if isinstance(obj, dict):
                rows.append(obj)
        except Exception:
            continue
    return rows


def event_time(e: dict[str, Any]) -> datetime | None:
    return parse_ts(e.get("timestamp") or e.get("ts"))


def uniq_keep_order(items: list[str]) -> list[str]:
    seen = set()
    out: list[str] = []
    for it in items:
        if it in seen:
            continue
        seen.add(it)
        out.append(it)
    return out


def infer_profiles(
    audit_ts: datetime | None,
    events: list[dict[str, Any]],
    near_minutes: int,
    fallback_hours: int,
    max_profiles: int,
) -> list[str]:
    if audit_ts is None:
        return []

    near_delta = timedelta(minutes=near_minutes)
    near = [
        e for e in events
        if (et := event_time(e)) is not None
        and abs(et - audit_ts) <= near_delta
        and e.get("profile_id")
    ]
    if near:
        profs = uniq_keep_order([str(e["profile_id"]) for e in sorted(near, key=event_time) if e.get("profile_id")])
        return profs[:max_profiles]

    lookback_from = audit_ts - timedelta(hours=fallback_hours)
    prev = [
        e for e in events
        if (et := event_time(e)) is not None
        and lookback_from <= et <= audit_ts
        and e.get("profile_id")
    ]
    if prev:
        # Prefer very recent context.
        profs = uniq_keep_order([str(e["profile_id"]) for e in sorted(prev, key=event_time, reverse=True) if e.get("profile_id")])
        return profs[:max_profiles]

    return []


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="Write back changes (default: dry-run)")
    ap.add_argument("--near-minutes", type=int, default=30)
    ap.add_argument("--fallback-hours", type=int, default=24)
    ap.add_argument("--max-profiles", type=int, default=3)
    ap.add_argument("--use-unknown", action="store_true", help="Set ['legacy-unknown'] when inference fails")
    args = ap.parse_args()

    audits = read_jsonl(AUDIT_PATH)
    events = read_jsonl(EVENTS_PATH)

    total = len(audits)
    missing_idx = [i for i, r in enumerate(audits) if not isinstance(r.get("profile_ids"), list) or len(r.get("profile_ids") or []) == 0]

    changed = 0
    inferred = 0
    unknown = 0

    for i in missing_idx:
        row = audits[i]
        ts = parse_ts(row.get("time"))
        pids = infer_profiles(ts, events, args.near_minutes, args.fallback_hours, args.max_profiles)
        if pids:
            row["profile_ids"] = pids
            inferred += 1
            changed += 1
        elif args.use_unknown:
            row["profile_ids"] = ["legacy-unknown"]
            unknown += 1
            changed += 1

    print(json.dumps({
        "ok": True,
        "audit_path": str(AUDIT_PATH),
        "events_path": str(EVENTS_PATH),
        "total_rows": total,
        "missing_before": len(missing_idx),
        "changed": changed,
        "inferred": inferred,
        "unknown_fallback": unknown,
        "dry_run": not args.apply,
    }, ensure_ascii=False))

    if args.apply and changed > 0:
        backup = AUDIT_PATH.with_suffix(AUDIT_PATH.suffix + f".bak-{datetime.now().strftime('%Y%m%d-%H%M%S')}")
        backup.write_text(AUDIT_PATH.read_text(encoding="utf-8"), encoding="utf-8")
        AUDIT_PATH.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in audits) + "\n", encoding="utf-8")
        print(json.dumps({"ok": True, "backup": str(backup), "written": changed}, ensure_ascii=False))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
