#!/usr/bin/env python3
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVENTS_PATH = ROOT / "lineage" / "events.jsonl"
OUT_PATH = ROOT / "lineage" / "generation_state.json"
HISTORY_PATH = ROOT / "lineage" / "generation_history.jsonl"


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


def append_history(record: dict):
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    with HISTORY_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def main():
    if not EVENTS_PATH.exists():
        raise SystemExit(f"missing file: {EVENTS_PATH}")

    events = load_events(EVENTS_PATH)
    candidates = [e for e in events if e.get("status") in {"PASS", "PASS*"}]
    if not candidates:
        raise SystemExit("no PASS/PASS* events")

    best = sorted(candidates, key=score_key, reverse=True)[0]
    now = datetime.now(timezone.utc).isoformat()

    state = {
        "version": "v0.2",
        "updated_at": now,
        "source": "promote_generation_seed.py",
        "source_event_id": best.get("event_id"),
        "last_promoted_at": now,
        "current_seed": {
            "event_id": best.get("event_id"),
            "wave_id": best.get("wave_id"),
            "profile_id": best.get("profile_id"),
            "score": best.get("score"),
            "status": best.get("status"),
            "timestamp": best.get("timestamp"),
        },
    }

    history_record = {
        "promoted_at": now,
        "source_event_id": best.get("event_id"),
        "wave_id": best.get("wave_id"),
        "profile_id": best.get("profile_id"),
        "score": best.get("score"),
        "status": best.get("status"),
        "event_timestamp": best.get("timestamp"),
    }

    OUT_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    append_history(history_record)

    print(str(OUT_PATH))
    print(str(HISTORY_PATH))


if __name__ == "__main__":
    main()
