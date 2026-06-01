#!/usr/bin/env python3
"""Public-safe template of the runtime calendar auto-classification script.

This version keeps the classification logic but replaces personal tokens and
calendar IDs with placeholders. Runtime truth lives in ~/.hermes/scripts.
"""
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

TOKEN = "${PRIMARY_GOOGLE_TOKEN_JSON}"
PRIMARY_CALENDAR_ID = "primary"
RANGE_MIN = "${RANGE_MIN_ISO}"
RANGE_MAX = "${RANGE_MAX_ISO}"

BUSINESS_KEYWORDS = ["회의", "미팅", "팀 회의", "네트워킹", "창업", "사업", "expo"]
RESEARCH_KEYWORDS = ["연구", "논문", "irb", "실험", "데이터"]
SPECIAL_KEYWORDS = ["세금", "신고", "결혼식", "마감", "취소"]
PERSONAL_KEYWORDS = ["여행", "런", "run", "축구", "숙소", "여권", "비행기", "환전", "보험"]


def classify(summary: str, desc: str = ""):
    text = f"{summary} {desc}".lower()
    if any(k in text for k in ["방문재활", "병원", "환자"]):
        return None
    if any(k in text for k in RESEARCH_KEYWORDS):
        return "연구"
    if any(k in text for k in SPECIAL_KEYWORDS):
        return "특수케이스"
    if any(k in text for k in BUSINESS_KEYWORDS):
        return "사업"
    if any(k in text for k in PERSONAL_KEYWORDS):
        return "개인"
    return None


def main() -> None:
    creds = Credentials.from_authorized_user_file(TOKEN)
    svc = build("calendar", "v3", credentials=creds, cache_discovery=False)

    calendars = svc.calendarList().list().execute().get("items", [])
    name_to_id = {item.get("summary"): item.get("id") for item in calendars}

    for name in ["사업", "연구", "개인", "특수케이스"]:
        if name not in name_to_id:
            created = svc.calendars().insert(body={"summary": name, "timeZone": "Asia/Seoul"}).execute()
            name_to_id[name] = created["id"]

    events = svc.events().list(
        calendarId=PRIMARY_CALENDAR_ID,
        timeMin=RANGE_MIN,
        timeMax=RANGE_MAX,
        singleEvents=True,
        orderBy="startTime",
        maxResults=250,
    ).execute().get("items", [])

    moved = 0
    for event in events:
        if event.get("status") == "cancelled":
            continue
        category = classify(event.get("summary", ""), event.get("description", ""))
        if not category:
            continue
        body = {
            key: value
            for key, value in event.items()
            if key in {
                "summary",
                "location",
                "description",
                "start",
                "end",
                "recurrence",
                "reminders",
                "attendees",
                "colorId",
                "transparency",
                "visibility",
            }
        }
        svc.events().insert(calendarId=name_to_id[category], body=body).execute()
        svc.events().delete(calendarId=PRIMARY_CALENDAR_ID, eventId=event["id"]).execute()
        moved += 1

    print(f"moved={moved}")


if __name__ == "__main__":
    main()
