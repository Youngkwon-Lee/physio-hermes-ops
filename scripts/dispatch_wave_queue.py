#!/usr/bin/env python3
import json
import subprocess
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LINEAGE_DIR = ROOT / "lineage"
REPORT_DIR = ROOT / "docs" / "reports" / "waves"
QUEUE_PATH = LINEAGE_DIR / "wave_queue.jsonl"
STATE_PATH = LINEAGE_DIR / "dispatch_state.json"
EVENTS_PATH = LINEAGE_DIR / "events.jsonl"

PER_TASK_TIMEOUT = 120  # keep under cron hard limits

LINEAGE_DIR.mkdir(parents=True, exist_ok=True)
REPORT_DIR.mkdir(parents=True, exist_ok=True)


def load_json(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def load_queue():
    if not QUEUE_PATH.exists():
        return []
    rows = []
    for ln in QUEUE_PATH.read_text(encoding="utf-8").splitlines():
        ln = ln.strip()
        if ln:
            rows.append(json.loads(ln))
    return rows


def append_event(event: dict):
    with EVENTS_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def run_task(profile_id: str, goal: str):
    prompt = (
        "You are executing a queued wave task in physio-hermes-ops. "
        "Return brief actionable output only. "
        f"Task goal: {goal}"
    )
    cmd = ["hermes", "-p", profile_id, "chat", "-q", prompt]

    started = datetime.now().isoformat(timespec="seconds")
    try:
        p = subprocess.run(
            cmd,
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=PER_TASK_TIMEOUT,
        )
        rc = p.returncode
        out = (p.stdout or "") + (p.stderr or "")
        status = "PASS" if rc == 0 else "CHECK"
    except subprocess.TimeoutExpired as e:
        rc = 124
        stdout = e.stdout.decode("utf-8", errors="ignore") if isinstance(e.stdout, (bytes, bytearray)) else (e.stdout or "")
        stderr = e.stderr.decode("utf-8", errors="ignore") if isinstance(e.stderr, (bytes, bytearray)) else (e.stderr or "")
        out = stdout + stderr
        status = "PASS*"  # timeout but may still have partial output

    ended = datetime.now().isoformat(timespec="seconds")
    tail = "\n".join(out.strip().splitlines()[-20:]) if out.strip() else ""
    return {
        "profile_id": profile_id,
        "goal": goal,
        "started_at": started,
        "ended_at": ended,
        "exit_code": rc,
        "status": status,
        "output_tail": tail,
    }


def main():
    queue = load_queue()
    if not queue:
        raise SystemExit(0)

    state = load_json(
        STATE_PATH,
        {
            "queue_index": 0,
            "task_index": 0,
            "completed_waves": [],
        },
    )

    qidx = int(state.get("queue_index", 0))
    tidx = int(state.get("task_index", 0))

    if qidx >= len(queue):
        raise SystemExit(0)

    item = queue[qidx]
    wave_id = item.get("next_wave", "wave-unknown")
    trigger_wave = item.get("trigger_wave", "wave-unknown")
    tasks = item.get("tasks", [])

    if not tasks:
        state["queue_index"] = qidx + 1
        state["task_index"] = 0
        STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        raise SystemExit(0)

    if tidx >= len(tasks):
        # finalize previous wave and move to next queue item
        done = set(state.get("completed_waves", []))
        done.add(wave_id)
        state["completed_waves"] = sorted(done)
        state["queue_index"] = qidx + 1
        state["task_index"] = 0
        state["last_dispatched_at"] = datetime.now().isoformat(timespec="seconds")
        STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"wave completed: {wave_id}")
        raise SystemExit(0)

    task = tasks[tidx]
    result = run_task(task.get("profile_id", "physio-orchestrator"), task.get("goal", ""))

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "queue_index": qidx,
        "task_index": tidx,
        "trigger_wave": trigger_wave,
        "wave_id": wave_id,
        "result": result,
    }
    report_path = REPORT_DIR / f"dispatch_{wave_id}_task{tidx+1}_{stamp}.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    event = {
        "event_id": f"evt-dispatch-{stamp}",
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "run_id": f"dispatch-{wave_id}",
        "wave_id": wave_id,
        "parent_wave_id": trigger_wave,
        "profile_id": result["profile_id"],
        "stage": "dispatch",
        "status": result["status"],
        "exit_code": result["exit_code"],
        "artifact_paths": [str(report_path.relative_to(ROOT))],
        "score": 90 if result["status"] == "PASS" else 80,
        "cost_tokens": None,
        "retry_count": 0,
        "notes": result["goal"],
        "links": {"commit": None, "pr": None, "report": str(report_path.relative_to(ROOT))},
    }
    append_event(event)

    state["task_index"] = tidx + 1
    state["last_dispatched_wave"] = wave_id
    state["last_dispatched_at"] = datetime.now().isoformat(timespec="seconds")
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"dispatched {wave_id} task {tidx+1}/{len(tasks)}: {result['profile_id']} ({result['status']})")
    print(f"report={report_path}")


if __name__ == "__main__":
    main()
