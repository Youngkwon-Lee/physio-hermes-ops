#!/usr/bin/env python3
import json
from datetime import datetime, timezone
from pathlib import Path

from lineage_stream_context import build_stream_context

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


def decision_to_event_status(decision: str) -> str:
    return {"GREEN": "PASS", "YELLOW": "CHECK", "RED": "FAIL"}.get(decision, "CHECK")


def append_close_event(all_events: list[dict], state: dict):
    latest_wave = state["wave_id"]
    run_id = f"generation-close-{latest_wave}"

    if any(e.get("run_id") == run_id for e in all_events):
        print(f"skip append: {run_id} already exists")
        return False

    decision = state["decision"]
    ts = state["closed_at"]
    event = {
        "event_id": f"evt-gen-close-{latest_wave}-{ts.replace(':', '').replace('-', '')[:15]}",
        "timestamp": ts,
        "run_id": run_id,
        "wave_id": latest_wave,
        "parent_wave_id": None,
        "profile_id": "physio-orchestrator",
        "stage": "orchestrate",
        "status": decision_to_event_status(decision),
        "exit_code": 0,
        "artifact_paths": ["lineage/generation_cycle_state.json"],
        "score": 90 if decision == "GREEN" else (80 if decision == "YELLOW" else 40),
        "cost_tokens": None,
        "retry_count": 0,
        "notes": f"generation cycle close decision={decision}",
        "links": {
            "commit": None,
            "pr": None,
            "report": "lineage/generation_cycle_state.json",
        },
    }
    event.update(build_stream_context(run_id))

    with EVENTS_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")

    print(f"appended close event: {event['event_id']}")
    return True


def main():
    if not EVENTS_PATH.exists():
        raise SystemExit(f"missing file: {EVENTS_PATH}")

    events = load_events()
    if not events:
        raise SystemExit("no events")

    latest_wave = max((e.get("wave_id") for e in events), key=wave_num)
    wave_events = [
        e for e in events
        if e.get("wave_id") == latest_wave and not str(e.get("run_id", "")).startswith("generation-close-")
    ]
    statuses = [e.get("status") for e in wave_events]

    state = {
        "version": "v0.5",
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
    append_close_event(events, state)
    print(str(OUT_PATH))


if __name__ == "__main__":
    main()
