#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

TOKEN = os.environ["PRIMARY_GOOGLE_TOKEN_JSON"]
PRIMARY = os.environ.get("PRIMARY_CALENDAR_ID", "primary")
RANGE_MIN = os.environ["RANGE_MIN_ISO"]
RANGE_MAX = os.environ["RANGE_MAX_ISO"]
MANIFEST_DIR = Path("/home/yk/physio-hermes-ops/dashboard/runtime/automation_job_manifests")
JOB_ID = "78831c1223ab"
JOB_NAME = "매일 23:10 캘린더 자동 분류"

business_kw = ["회의", "미팅", "팀 회의", "네트워킹", "창업", "사업", "코디세이", "expo"]
research_kw = ["연구", "논문", "irb", "실험", "데이터"]
special_kw = ["연말정산", "세금", "신고", "결혼식", "마감", "취소"]
personal_kw = ["여행", "발리", "런", "run", "축구", "숙소", "여권", "비행기", "환전", "보험", "차키", "애플워치"]


def utc_now() -> datetime:
    return datetime.now(UTC)


def write_manifest(started_at: datetime, result: dict, errors: list[str] | None = None) -> None:
    errors = errors or []
    payload = {
        "schemaVersion": 1,
        "evidenceSource": "runtime-direct",
        "generatedAt": utc_now().isoformat(),
        "runStartedAt": started_at.isoformat(),
        "runFinishedAt": utc_now().isoformat(),
        "status": "error" if errors else "ok",
        "job": {"id": JOB_ID, "name": JOB_NAME, "runtime": "hermes-script"},
        "createdFiles": [],
        "notionPages": [],
        "discordMessages": [],
        "artifacts": [],
        "errors": errors,
        "metadata": result,
    }
    MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
    path = MANIFEST_DIR / f"{JOB_ID}.json"
    tmp_path = path.with_suffix(".json.tmp")
    tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp_path.replace(path)


def classify(summary: str, desc: str = ""):
    t = f"{summary} {desc}".lower()
    if any(k in t for k in ["방문재활", "병원", "환자"]):
        return None
    if any(k in t for k in research_kw):
        return "연구"
    if any(k in t for k in special_kw):
        return "특수케이스"
    if any(k in t for k in business_kw):
        return "사업"
    if any(k in t for k in personal_kw):
        return "개인"
    return None


def run() -> dict:
    creds = Credentials.from_authorized_user_file(TOKEN)
    svc = build("calendar", "v3", credentials=creds, cache_discovery=False)

    cals = svc.calendarList().list().execute().get("items", [])
    name_to_id = {c.get("summary"): c.get("id") for c in cals}
    created_calendars: list[str] = []

    for name in ["사업", "연구", "개인", "특수케이스"]:
        if name not in name_to_id:
            created = svc.calendars().insert(body={"summary": name, "timeZone": "Asia/Seoul"}).execute()
            name_to_id[name] = created["id"]
            created_calendars.append(name)

    events = svc.events().list(
        calendarId=PRIMARY,
        timeMin=RANGE_MIN,
        timeMax=RANGE_MAX,
        singleEvents=True,
        orderBy="startTime",
        maxResults=250,
    ).execute().get("items", [])

    moved = 0
    skipped_cancelled = 0
    skipped_unclassified = 0
    moved_by_category: dict[str, int] = {}
    moved_events: list[dict] = []

    for e in events:
        if e.get("status") == "cancelled":
            skipped_cancelled += 1
            continue
        summary = e.get("summary", "")
        desc = e.get("description", "")
        cat = classify(summary, desc)
        if not cat:
            skipped_unclassified += 1
            continue

        body = {k: v for k, v in e.items() if k in [
            "summary", "location", "description", "start", "end",
            "recurrence", "reminders", "attendees", "colorId",
            "transparency", "visibility",
        ]}
        inserted = svc.events().insert(calendarId=name_to_id[cat], body=body).execute()
        svc.events().delete(calendarId=PRIMARY, eventId=e["id"]).execute()
        moved += 1
        moved_by_category[cat] = moved_by_category.get(cat, 0) + 1
        moved_events.append({
            "summary": summary,
            "category": cat,
            "sourceEventId": e.get("id"),
            "targetEventId": inserted.get("id"),
            "start": e.get("start"),
        })

    return {
        "primaryCalendar": PRIMARY,
        "rangeMin": RANGE_MIN,
        "rangeMax": RANGE_MAX,
        "eventsScanned": len(events),
        "moved": moved,
        "movedByCategory": moved_by_category,
        "movedEvents": moved_events[:50],
        "skippedCancelled": skipped_cancelled,
        "skippedUnclassified": skipped_unclassified,
        "createdCalendars": created_calendars,
    }


def main() -> int:
    started_at = utc_now()
    try:
        result = run()
    except Exception as exc:
        write_manifest(started_at, {"primaryCalendar": PRIMARY, "rangeMin": RANGE_MIN, "rangeMax": RANGE_MAX}, [str(exc)])
        raise
    write_manifest(started_at, result)
    print(f"moved={result['moved']} scanned={result['eventsScanned']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
