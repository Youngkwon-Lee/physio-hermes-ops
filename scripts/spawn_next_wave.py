#!/usr/bin/env python3
import json
from datetime import datetime
from pathlib import Path

root = Path(__file__).resolve().parents[1]
lineage_path = root / 'lineage' / 'events.jsonl'
queue_path = root / 'lineage' / 'wave_queue.jsonl'
state_path = root / 'lineage' / 'spawn_state.json'

root.joinpath('lineage').mkdir(parents=True, exist_ok=True)

def load_events():
    rows=[]
    if not lineage_path.exists():
        return rows
    for ln in lineage_path.read_text(encoding='utf-8').splitlines():
        ln=ln.strip()
        if ln:
            rows.append(json.loads(ln))
    return rows

def load_state():
    if not state_path.exists():
        return {"last_wave": 0}
    return json.loads(state_path.read_text(encoding='utf-8'))

rows = load_events()
if not rows:
    raise SystemExit(0)  # silent

wave_ids=[]
for r in rows:
    w=r.get('wave_id','')
    if isinstance(w,str) and w.startswith('wave-'):
        try:
            wave_ids.append(int(w.split('-')[1]))
        except Exception:
            pass
if not wave_ids:
    raise SystemExit(0)

current_wave=max(wave_ids)
state=load_state()
last_wave=int(state.get('last_wave',0))
if current_wave <= last_wave:
    raise SystemExit(0)  # already spawned for this wave

# Seed selection rule (lightweight): highest score event in current wave
current=[r for r in rows if r.get('wave_id')==f'wave-{current_wave}']
if not current:
    raise SystemExit(0)
best=max(current,key=lambda r: float(r.get('score',0)))
next_wave=current_wave+1

payload={
    "created_at": datetime.now().isoformat(timespec='seconds'),
    "trigger_wave": f"wave-{current_wave}",
    "next_wave": f"wave-{next_wave}",
    "seed": {
        "event_id": best.get('event_id'),
        "profile_id": best.get('profile_id'),
        "score": best.get('score'),
        "status": best.get('status')
    },
    "tasks": [
        {"profile_id":"physio-planner","goal":"Refine next wave task spec from previous best seed"},
        {"profile_id":"physio-frontend","goal":"Polish UI tasks from seed scope"},
        {"profile_id":"physio-backend","goal":"Harden backend logic from seed scope"},
        {"profile_id":"physio-qa","goal":"Verify PASS/PASS* criteria and produce evidence"},
        {"profile_id":"physio-orchestrator","goal":"Aggregate and decide GREEN/YELLOW/RED"}
    ]
}

with queue_path.open('a', encoding='utf-8') as f:
    f.write(json.dumps(payload, ensure_ascii=False) + "\n")

state['last_wave']=current_wave
state['last_spawned_at']=datetime.now().isoformat(timespec='seconds')
state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')

print(f"spawned next wave: wave-{next_wave} from wave-{current_wave}, seed={best.get('event_id')}")
