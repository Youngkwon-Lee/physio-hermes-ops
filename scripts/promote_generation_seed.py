#!/usr/bin/env python3
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVENTS_PATH = ROOT / "lineage" / "events.jsonl"
OUT_PATH = ROOT / "lineage" / "generation_state.json"


def load_events(path: Path):
    events = []
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s:
            continue
        events.append(json.loads(s))
    return events


def score_key(e: dict):
    score = float(e.get("score", -1))
    ts = str(e.get("timestamp", ""))
    return (score, ts)


def main():
    if not EVENTS_PATH.exists():
        raise SystemExit(f"missing file: {EVENTS_PATH}")

    events = load_events(EVENTS_PATH)
    candidates = [e for e in events if e.get("status") in {"PASS", "PASS*"}]
    if not candidates:
        raise SystemExit("no PASS/PASS* events")

    best = sorted(candidates, key=score_key, reverse=True)[0]

    state = {
        "version": "v0.1",
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "source": "promote_generation_seed.py",
        "source_event_id": best.get("event_id"),
        "last_promoted_at": datetime.now(timezone.utc).isoformat(),
        "current_seed": {
            "event_id": best.get("event_id"),
            "wave_id": best.get("wave_id"),
            "profile_id": best.get("profile_id"),
            "score": best.get("score"),
            "status": best.get("status"),
            "timestamp": best.get("timestamp"),
        },
    }

    OUT_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(str(OUT_PATH))


if __name__ == "__main__":
    main()
