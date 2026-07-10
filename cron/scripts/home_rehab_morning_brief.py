#!/usr/bin/env python3
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from google.auth.exceptions import RefreshError
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

TOKEN_FILE = os.environ.get("GOOGLE_CALENDAR_TOKEN_FILE") or "${GOOGLE_CALENDAR_TOKEN_FILE}"
TIMEZONE = "Asia/Seoul"
CALENDAR_NAME = os.environ.get("HOME_REHAB_CALENDAR_NAME", "방문재활")
CALENDAR_ID = os.environ.get("HOME_REHAB_CALENDAR_ID") or "${HOME_REHAB_CALENDAR_ID}"
ACCOUNT_LABEL = os.environ.get("HOME_REHAB_ACCOUNT_LABEL", "configured Google account")
LUNCH_KEYWORDS = ("점심", "런치", "식사", "lunch")


@dataclass(frozen=True, slots=True)
class RehabEvent:
    summary: str
    location: str
    start: datetime
    end: datetime


def configured_value(value: str, name: str) -> str:
    if not value or value == f"${{{name}}}":
        raise RuntimeError(f"{name} is not configured")
    return value


def is_lunch(summary: str) -> bool:
    text = summary.strip().lower()
    return any(keyword in text for keyword in LUNCH_KEYWORDS)


def parse_dt(value: str, tz: ZoneInfo) -> datetime:
    if "T" in value:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt.astimezone(tz)
    return datetime.fromisoformat(value).replace(tzinfo=tz)


def fmt_hm(dt: datetime) -> str:
    return dt.strftime("%H:%M")


def fmt_gap(minutes: int) -> str:
    hours, remainder = divmod(minutes, 60)
    if hours and remainder:
        return f"{hours}시간 {remainder}분"
    if hours:
        return f"{hours}시간"
    return f"{remainder}분"


def build_service():
    token_file = configured_value(TOKEN_FILE, "GOOGLE_CALENDAR_TOKEN_FILE")
    credentials = Credentials.from_authorized_user_file(token_file)
    return build("calendar", "v3", credentials=credentials)


def fetch_events(service, start: datetime, end: datetime) -> list[RehabEvent]:
    calendar_id = configured_value(CALENDAR_ID, "HOME_REHAB_CALENDAR_ID")
    items = (
        service.events()
        .list(
            calendarId=calendar_id,
            timeMin=start.isoformat(),
            timeMax=end.isoformat(),
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
        .get("items", [])
    )
    events: list[RehabEvent] = []
    tz = ZoneInfo(TIMEZONE)
    for item in items:
        summary = item.get("summary", "(제목없음)")
        if is_lunch(summary):
            continue
        start_raw = item.get("start", {}).get("dateTime") or item.get("start", {}).get("date")
        end_raw = item.get("end", {}).get("dateTime") or item.get("end", {}).get("date")
        if not start_raw or not end_raw:
            continue
        events.append(
            RehabEvent(
                summary=summary,
                location=(item.get("location") or "").strip(),
                start=parse_dt(start_raw, tz),
                end=parse_dt(end_raw, tz),
            )
        )
    return sorted(events, key=lambda event: event.start)


def render_empty(day: datetime) -> str:
    lines = report_header(day, 0)
    lines.extend(
        [
            "",
            "## 오늘 일정",
            "- 일정 없음",
            "",
            "## 이동/간격 포인트",
            "- 계산 대상 없음",
            "",
            "## 준비 체크포인트",
            "- 없음",
            "",
            "## 특이사항",
            "- 점심/런치/식사 성격 일정은 자동 제외",
        ]
    )
    return "\n".join(lines)


def report_header(day: datetime, count: int) -> list[str]:
    return [
        "# 방문재활 아침 브리핑",
        f"- 기준 계정: {ACCOUNT_LABEL}",
        f"- 기준 캘린더: {CALENDAR_NAME}",
        f"- 날짜: {day.strftime('%Y-%m-%d')} ({TIMEZONE})",
        f"- 요약: 방문재활 일정 {count}건",
    ]


def render_schedule(lines: list[str], events: list[RehabEvent]) -> None:
    lines.extend(["", "## 오늘 일정"])
    for event in events:
        location = f" | {event.location}" if event.location else ""
        lines.append(f"- {fmt_hm(event.start)}-{fmt_hm(event.end)} | {event.summary}{location}")


def render_gaps(lines: list[str], events: list[RehabEvent]) -> None:
    lines.extend(["", "## 이동/간격 포인트"])
    if len(events) == 1:
        lines.append("- 단일 일정이라 일정 간 간격 계산 없음")
        return
    for previous, current in zip(events, events[1:]):
        gap_minutes = int((current.start - previous.end).total_seconds() // 60)
        if gap_minutes < 0:
            lines.append(
                f"- 겹침: {fmt_hm(previous.end)} 종료 예정 -> "
                f"{fmt_hm(current.start)} 시작 ({abs(gap_minutes)}분 중첩)"
            )
        else:
            lines.append(
                f"- {fmt_hm(previous.end)} 종료 -> {fmt_hm(current.start)} 시작: "
                f"{fmt_gap(gap_minutes)}"
            )


def render_checkpoints(lines: list[str], events: list[RehabEvent]) -> None:
    lines.extend(["", "## 준비 체크포인트"])
    first = events[0]
    if first.location:
        lines.append(f"- 첫 일정 위치 확인: {first.location}")
    else:
        lines.append("- 첫 일정 위치 미기재: 출발 전 주소/장소 재확인 필요")
    if len(events) == 1:
        lines.append("- 일정 1건: 이동 버퍼 압박 낮음")
        return
    shortest_gap = min(
        int((current.start - previous.end).total_seconds() // 60)
        for previous, current in zip(events, events[1:])
    )
    if shortest_gap < 20:
        lines.append(f"- 일정 간 최소 간격 {shortest_gap}분: 이동/버퍼 촘촘함")
    else:
        lines.append(f"- 일정 간 최소 간격 {shortest_gap}분")


def render_notes(lines: list[str], events: list[RehabEvent]) -> None:
    lines.extend(["", "## 특이사항"])
    overlap_count = sum(1 for previous, current in zip(events, events[1:]) if current.start < previous.end)
    if overlap_count:
        lines.append(f"- 겹치는 일정 {overlap_count}건 구간 존재")
    else:
        lines.append("- 일정 겹침 없음")
    lines.append("- 점심/런치/식사 성격 일정은 자동 제외")


def render_report(events: list[RehabEvent], day: datetime) -> str:
    if not events:
        return render_empty(day)
    lines = report_header(day, len(events))
    render_schedule(lines, events)
    render_gaps(lines, events)
    render_checkpoints(lines, events)
    render_notes(lines, events)
    return "\n".join(lines)


def render_runtime_error(day: datetime, summary: str, detail: str) -> str:
    lines = [
        "# 방문재활 아침 브리핑",
        f"- 기준 계정: {ACCOUNT_LABEL}",
        f"- 기준 캘린더: {CALENDAR_NAME}",
        f"- 날짜: {day.strftime('%Y-%m-%d')} ({TIMEZONE})",
        f"- 요약: {summary}",
        "",
        "## 오늘 일정",
        "- 일정 조회 실패",
        "",
        "## 이동/간격 포인트",
        "- 오늘 일정을 조회할 수 없어 계산 대상 없음",
        "",
        "## 준비 체크포인트",
        "- Google Calendar 인증과 환경 변수를 확인하세요.",
        "",
        "## 특이사항",
        f"- 오류: {detail}",
    ]
    return "\n".join(lines)


def main() -> None:
    tz = ZoneInfo(TIMEZONE)
    start = datetime.now(tz).replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)
    try:
        service = build_service()
        events = fetch_events(service, start, end)
        print(render_report(events, start))
    except RefreshError as exc:
        print(render_runtime_error(start, "Google 인증 갱신 필요", str(exc).splitlines()[0]))
    except (HttpError, OSError, RuntimeError, ValueError) as exc:
        print(render_runtime_error(start, "스크립트 오류로 브리핑 생성 실패", str(exc).splitlines()[0]))


if __name__ == "__main__":
    main()
