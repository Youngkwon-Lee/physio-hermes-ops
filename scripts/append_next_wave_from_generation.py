#!/usr/bin/env python3
import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GEN_PATH = ROOT / "lineage" / "generation_state.json"
QUEUE_PATH = ROOT / "lineage" / "wave_queue.jsonl"
SPAWN_STATE = ROOT / "lineage" / "spawn_state.json"


def read_json(path: Path, default=None):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path):
    rows = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if s:
            rows.append(json.loads(s))
    return rows


def wave_num(w):
    if isinstance(w, str) and w.startswith("wave-"):
        try:
            return int(w.split("-")[1])
        except Exception:
            return 0
    return 0


def main():
    gen = read_json(GEN_PATH, {})
    seed = (gen or {}).get("current_seed") or {}
    seed_wave = seed.get("wave_id")
    if not seed_wave:
        raise SystemExit("no generation seed wave_id")

    qrows = read_jsonl(QUEUE_PATH)

    max_seed_wave = wave_num(seed_wave)
    max_queue_next = max([wave_num(r.get("next_wave")) for r in qrows] + [0])
    max_trigger_wave = max([wave_num(r.get("trigger_wave")) for r in qrows] + [0])
    baseline = max(max_seed_wave, max_queue_next, max_trigger_wave)

    next_wave_n = baseline + 1
    next_wave = f"wave-{next_wave_n}"

    if any(r.get("next_wave") == next_wave for r in qrows):
        print(f"skip: {next_wave} already queued")
        return

    payload = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "trigger_wave": f"wave-{baseline}",
        "next_wave": next_wave,
        "seed": {
            "event_id": seed.get("event_id"),
            "profile_id": seed.get("profile_id"),
            "score": seed.get("score"),
            "status": seed.get("status"),
        },
        "tasks": [
            {"profile_id": "physio-planner", "goal": "Refine next wave task spec from promoted generation seed"},
            {"profile_id": "physio-frontend", "goal": "Apply UI polish tasks from generation seed"},
            {"profile_id": "physio-backend", "goal": "Apply backend hardening tasks from generation seed"},
            {"profile_id": "physio-qa", "goal": "Validate PASS/PASS*/CHECK/FAIL evidence for this wave"},
            {"profile_id": "physio-orchestrator", "goal": "Auto-close wave and publish final loop decision"},
        ],
    }

    with QUEUE_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")

    st = read_json(SPAWN_STATE, {"last_wave": 0}) or {"last_wave": 0}
    st["last_wave"] = baseline
    st["last_spawned_at"] = datetime.now().isoformat(timespec="seconds")
    SPAWN_STATE.write_text(json.dumps(st, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"queued {next_wave} from seed {seed.get('event_id')}")


if __name__ == "__main__":
    main()
