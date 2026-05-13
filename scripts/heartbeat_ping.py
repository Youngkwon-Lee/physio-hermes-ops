#!/usr/bin/env python3
import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LINEAGE = ROOT / "lineage"
OUT = LINEAGE / "heartbeat.json"
EVENTS = LINEAGE / "events.jsonl"
STATE = LINEAGE / "dispatch_state.json"

LINEAGE.mkdir(parents=True, exist_ok=True)

last_event_at = None
last_wave = None
event_count = 0
if EVENTS.exists():
    rows = [ln.strip() for ln in EVENTS.read_text(encoding="utf-8").splitlines() if ln.strip()]
    event_count = len(rows)
    if rows:
        last = json.loads(rows[-1])
        last_event_at = last.get("timestamp") or last.get("ts")
        last_wave = last.get("wave_id")

state = {}
if STATE.exists():
    state = json.loads(STATE.read_text(encoding="utf-8"))

payload = {
    "generated_at": datetime.now().isoformat(timespec="seconds"),
    "alive": True,
    "source": "physio-heartbeat",
    "event_count": event_count,
    "last_event_at": last_event_at,
    "last_wave": last_wave,
    "dispatch_cursor": {
        "queue_index": state.get("queue_index"),
        "task_index": state.get("task_index"),
        "last_dispatched_at": state.get("last_dispatched_at"),
    }
}
OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
print(str(OUT))
