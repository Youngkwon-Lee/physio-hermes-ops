#!/usr/bin/env python3
import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LINEAGE = ROOT / "lineage"
LINEAGE.mkdir(parents=True, exist_ok=True)

STATE_PATH = LINEAGE / "ralph_loop_state.json"
HB_PATH = LINEAGE / "heartbeat.json"
CRON_PATH = ROOT / "dashboard" / "cron_status.json"

state = {
    "generated_at": datetime.now().isoformat(timespec="seconds"),
    "loop_name": "ralph",
    "alive": True,
    "mode": "paused-safe",
    "signals": {
        "heartbeat_alive": None,
        "spawn_state": None,
        "dispatch_state": None
    },
    "summary": ""
}

try:
    hb = json.loads(HB_PATH.read_text(encoding="utf-8")) if HB_PATH.exists() else {}
    state["signals"]["heartbeat_alive"] = hb.get("alive")
except Exception:
    pass

try:
    cr = json.loads(CRON_PATH.read_text(encoding="utf-8")) if CRON_PATH.exists() else {}
    items = cr.get("items", {})
    state["signals"]["spawn_state"] = (items.get("wave_spawn") or {}).get("state")
    state["signals"]["dispatch_state"] = (items.get("wave_dispatcher") or {}).get("state")
except Exception:
    pass

hb_ok = state["signals"].get("heartbeat_alive") is True
sp = state["signals"].get("spawn_state")
dp = state["signals"].get("dispatch_state")
if hb_ok and sp == "paused" and dp == "paused":
    state["summary"] = "ralph loop standby healthy (heartbeat alive, spawn/dispatch paused)"
else:
    state["summary"] = "ralph loop attention needed"

STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
print(str(STATE_PATH))
