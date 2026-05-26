#!/usr/bin/env python3
import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LINEAGE_DIR = ROOT / "lineage"
OUT_DIR = ROOT / "dashboard" / "derived"

PROFILE_LABELS = {
    "physio-orchestrator": "오케스트레이터",
    "physio-planner": "기획자",
    "physio-frontend": "프론트엔드",
    "physio-backend": "백엔드",
    "physio-qa": "QA",
    "physio-designer": "디자이너",
    "physio-marketing": "마케팅",
    "physio-ops-reporter": "운영 리포터",
}

STAGE_TO_ROOM = {
    "plan": ("plan-room", "기획실", "plan"),
    "build": ("build-room", "개발실", "build"),
    "verify": ("qa-room", "QA룸", "verify"),
    "report": ("ops-room", "운영실", "report"),
    "dispatch": ("dispatch-room", "배차실", "dispatch"),
    "orchestrate": ("orchestrator-room", "오케스트레이션 룸", "orchestrate"),
}

STREAM_LABELS = {
    "physio_bot": "메인 작업방",
    "overnight": "야간 자동화실",
    "mem": "메모리/기록실",
}


def now_iso():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def parse_args():
    parser = argparse.ArgumentParser(description="Build dashboard read-model JSON files.")
    parser.add_argument("--event-limit", type=int, default=200, help="How many recent events to read")
    return parser.parse_args()


def read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def read_jsonl(path: Path):
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except Exception:
            continue
    return out


def parse_ts(value):
    if not value:
        return datetime.min
    text = str(value).strip()
    if not text:
        return datetime.min
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        pass
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return datetime.min


def comparable_ts(value):
    dt = parse_ts(value)
    if dt.tzinfo is not None:
        dt = dt.astimezone().replace(tzinfo=None)
    return dt


def sort_events(events):
    return sorted(events, key=lambda row: (comparable_ts(row.get("timestamp")), str(row.get("event_id", ""))))


def stage_room(stage):
    return STAGE_TO_ROOM.get(stage or "", ("unknown-room", "미분류", "unknown"))


def stream_label(stream_id):
    return STREAM_LABELS.get(stream_id, stream_id or "unknown")


def status_rank(status):
    order = {"FAIL": 4, "CHECK": 3, "PASS*": 2, "PASS": 1}
    return order.get(str(status or "").upper(), 0)


def build_profile_snapshot(events):
    latest = {}
    for event in events:
        profile_id = event.get("profile_id")
        if not profile_id:
            continue
        current = latest.get(profile_id)
        if current is None or comparable_ts(event.get("timestamp")) >= comparable_ts(current.get("timestamp")):
            latest[profile_id] = event
    return latest


def build_rooms(latest_by_profile, latest_wave_id, event_limit):
    grouped = {}
    for profile_id, event in latest_by_profile.items():
        room_id, name, stage_group = stage_room(event.get("stage"))
        item = grouped.setdefault(
            room_id,
            {
                "room_id": room_id,
                "name": name,
                "stream_id": event.get("stream_id") or "unknown",
                "stream_label": stream_label(event.get("stream_id")),
                "stage_group": stage_group,
                "capacity": 0,
                "active_count": 0,
                "check_count": 0,
                "fail_count": 0,
                "dominant_status": "PASS",
                "profiles": [],
                "latest_wave_id": latest_wave_id,
            },
        )
        item["capacity"] += 1
        item["active_count"] += 1
        item["profiles"].append(profile_id)
        status = str(event.get("status") or "").upper()
        if status == "CHECK":
            item["check_count"] += 1
        if status == "FAIL":
            item["fail_count"] += 1
        if status_rank(status) > status_rank(item["dominant_status"]):
            item["dominant_status"] = status

    items = sorted(grouped.values(), key=lambda row: row["room_id"])
    return {
        "generated_at": now_iso(),
        "source_window": {"event_limit": event_limit, "latest_wave_id": latest_wave_id},
        "items": items,
    }


def build_seats(latest_by_profile):
    items = []
    for profile_id, event in sorted(latest_by_profile.items()):
        room_id, _, _ = stage_room(event.get("stage"))
        items.append(
            {
                "seat_id": f"{room_id}:{profile_id}",
                "room_id": room_id,
                "profile_id": profile_id,
                "display_name": PROFILE_LABELS.get(profile_id, profile_id),
                "stream_id": event.get("stream_id"),
                "stream_label": stream_label(event.get("stream_id")),
                "stage": event.get("stage"),
                "status": event.get("status"),
                "wave_id": event.get("wave_id"),
                "score": event.get("score"),
                "retry_count": event.get("retry_count"),
                "cost_tokens": event.get("cost_tokens"),
                "summary": event.get("notes") or "",
                "last_event_at": event.get("timestamp"),
                "links": event.get("links") or {"commit": None, "pr": None, "report": None},
            }
        )
    return {"generated_at": now_iso(), "items": items}


def build_help_queue(events):
    items = []
    for event in reversed(events):
        status = str(event.get("status") or "").upper()
        if status not in {"CHECK", "FAIL"}:
            continue
        priority = "high" if status == "FAIL" else "medium"
        items.append(
            {
                "id": event.get("event_id"),
                "priority": priority,
                "status": status,
                "profile_id": event.get("profile_id"),
                "display_name": PROFILE_LABELS.get(event.get("profile_id"), event.get("profile_id")),
                "stream_id": event.get("stream_id"),
                "stream_label": stream_label(event.get("stream_id")),
                "wave_id": event.get("wave_id"),
                "stage": event.get("stage"),
                "summary": event.get("notes") or "",
                "retry_count": event.get("retry_count"),
                "last_event_at": event.get("timestamp"),
                "artifact_paths": event.get("artifact_paths") or [],
            }
        )
    return {"generated_at": now_iso(), "items": items}


def build_showcase(events):
    seen = set()
    scored = sorted(events, key=lambda row: (float(row.get("score") or 0), comparable_ts(row.get("timestamp"))), reverse=True)
    items = []
    for event in scored:
        profile_id = event.get("profile_id")
        wave_id = event.get("wave_id")
        key = (profile_id, wave_id)
        links = event.get("links") or {}
        has_showcase_signal = bool(links.get("commit") or links.get("pr") or links.get("report") or event.get("artifact_paths"))
        if key in seen or not has_showcase_signal:
            continue
        seen.add(key)
        items.append(
            {
                "id": f"showcase:{wave_id}:{profile_id}",
                "profile_id": profile_id,
                "display_name": PROFILE_LABELS.get(profile_id, profile_id),
                "wave_id": wave_id,
                "score": event.get("score"),
                "title": event.get("notes") or f"{profile_id} result",
                "summary": event.get("notes") or "",
                "links": links,
                "artifact_paths": event.get("artifact_paths") or [],
                "published_at": event.get("timestamp"),
            }
        )
        if len(items) >= 12:
            break
    return {"generated_at": now_iso(), "items": items}


def build_feed(events):
    grouped = defaultdict(list)
    for event in reversed(events):
        stream_id = event.get("stream_id") or "unknown"
        grouped[stream_id].append(
            {
                "event_id": event.get("event_id"),
                "profile_id": event.get("profile_id"),
                "display_name": PROFILE_LABELS.get(event.get("profile_id"), event.get("profile_id")),
                "status": event.get("status"),
                "wave_id": event.get("wave_id"),
                "summary": event.get("notes") or "",
                "timestamp": event.get("timestamp"),
            }
        )
    items = []
    for stream_id in sorted(grouped):
        items.append(
            {
                "stream_id": stream_id,
                "stream_label": stream_label(stream_id),
                "items": grouped[stream_id][:5],
            }
        )
    return {"generated_at": now_iso(), "items": items}


def build_kpis(events, latest_wave_id):
    counts = Counter(str(event.get("status") or "").upper() for event in events)
    avg_score = 0.0
    if events:
        avg_score = sum(float(event.get("score") or 0) for event in events) / len(events)
    streams = {event.get("stream_id") for event in events if event.get("stream_id")}
    profiles = {event.get("profile_id") for event in events if event.get("profile_id")}
    return {
        "generated_at": now_iso(),
        "summary": {
            "active_profiles": len(profiles),
            "active_streams": len(streams),
            "pass_count": counts.get("PASS", 0) + counts.get("PASS*", 0),
            "check_count": counts.get("CHECK", 0),
            "fail_count": counts.get("FAIL", 0),
            "latest_wave_id": latest_wave_id,
            "avg_score": round(avg_score, 1),
        },
    }


def build_ops_snapshot(events):
    generation = read_json(LINEAGE_DIR / "generation_cycle_state.json", {})
    heartbeat = read_json(LINEAGE_DIR / "heartbeat.json", {})
    spawn = read_json(LINEAGE_DIR / "spawn_state.json", {})
    dispatch = read_json(LINEAGE_DIR / "dispatch_state.json", {})

    recent = events[-12:]
    fail_n = sum(1 for event in recent if str(event.get("status") or "").upper() == "FAIL")
    check_n = sum(1 for event in recent if str(event.get("status") or "").upper() == "CHECK")
    decision = str(generation.get("decision", "UNKNOWN")).upper()
    alive = bool(heartbeat.get("alive", True))
    if not alive:
        fsm_state = "HALTED"
        reason = "heartbeat down"
    elif fail_n > 0 or decision == "RED":
        fsm_state = "DEGRADED"
        reason = f"decision={decision}, fail={fail_n}"
    elif check_n > 0 or decision == "YELLOW":
        fsm_state = "CAUTION"
        reason = f"decision={decision}, check={check_n}"
    elif str(spawn.get("state", "")).lower() == "scheduled" and str(dispatch.get("state", "")).lower() == "scheduled":
        fsm_state = "RUNNING"
        reason = "spawn/dispatch scheduled"
    else:
        fsm_state = "IDLE"
        reason = "no active scheduling signal"

    if decision == "RED" or fail_n > 0:
        recommendation = "HOLD"
    elif decision == "YELLOW" or check_n > 0:
        recommendation = "LIMITED_RESUME"
    elif decision == "GREEN" and fail_n == 0 and check_n == 0:
        recommendation = "RESUME"
    else:
        recommendation = "CHECK_REQUIRED"

    return {
        "generated_at": now_iso(),
        "fsm": {"state": fsm_state, "reason": reason},
        "generation": {
            "decision": decision,
            "resume_recommendation": recommendation,
            "status_breakdown": generation.get("status_breakdown") or {},
            "wave_id": generation.get("wave_id"),
        },
        "heartbeat": heartbeat,
        "spawn_state": spawn,
        "dispatch_state": dispatch,
        "actions": ["refresh", "pause_all", "resume_core", "finalize_once"],
    }


def write_json(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main():
    args = parse_args()
    events = sort_events(read_jsonl(LINEAGE_DIR / "events.jsonl"))[-args.event_limit :]
    latest_wave_id = events[-1].get("wave_id") if events else None
    latest_by_profile = build_profile_snapshot(events)

    write_json(OUT_DIR / "rooms.json", build_rooms(latest_by_profile, latest_wave_id, args.event_limit))
    write_json(OUT_DIR / "seats.json", build_seats(latest_by_profile))
    write_json(OUT_DIR / "help_queue.json", build_help_queue(events))
    write_json(OUT_DIR / "showcase.json", build_showcase(events))
    write_json(OUT_DIR / "ops_snapshot.json", build_ops_snapshot(events))
    write_json(OUT_DIR / "feed.json", build_feed(events))
    write_json(OUT_DIR / "kpis.json", build_kpis(events, latest_wave_id))
    print(str(OUT_DIR))


if __name__ == "__main__":
    main()
