#!/usr/bin/env python3
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVENTS_PATH = ROOT / "lineage" / "events.jsonl"
OUT_PATH = ROOT / "lineage" / "generation_cycle_state.json"


def load_events():
    rows = []
    for line in EVENTS_PATH.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if s:
            rows.append(json.loads(s))
    return rows


def wave_num(w):
    if isinstance(w, str) and w.startswith("wave-"):
        try:
            return int(w.split("-")[1])
        except Exception:
            return -1
    return -1


def close_status(statuses):
    s = set(statuses)
    if "FAIL" in s:
        return "RED"
    if "CHECK" in s or "PASS*" in s:
        return "YELLOW"
    return "GREEN"


def main():
    if not EVENTS_PATH.exists():
        raise SystemExit(f"missing file: {EVENTS_PATH}")

    events = load_events()
    if not events:
        raise SystemExit("no events")

    latest_wave = max((e.get("wave_id") for e in events), key=wave_num)
    wave_events = [e for e in events if e.get("wave_id") == latest_wave]
    statuses = [e.get("status") for e in wave_events]

    state = {
        "version": "v0.3",
        "closed_at": datetime.now(timezone.utc).isoformat(),
        "wave_id": latest_wave,
        "event_count": len(wave_events),
        "decision": close_status(statuses),
        "status_breakdown": {
            "PASS": statuses.count("PASS"),
            "PASS*": statuses.count("PASS*"),
            "CHECK": statuses.count("CHECK"),
            "FAIL": statuses.count("FAIL"),
        },
        "source": "close_generation_cycle.py",
    }

    OUT_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(str(OUT_PATH))


if __name__ == "__main__":
    main()
