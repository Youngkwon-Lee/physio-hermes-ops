#!/usr/bin/env python3
"""Public-safe template of the runtime daily calendar + mail morning brief script.

This file intentionally generalizes credentials, account IDs, and some local paths.
Runtime truth lives in ~/.hermes/scripts/daily_calendar_mail_brief.py.
"""
from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

KST = ZoneInfo("Asia/Seoul")
PRIMARY_TOKEN = Path("${PRIMARY_GOOGLE_TOKEN_JSON}")
SECONDARY_TOKEN = Path("${SECONDARY_GOOGLE_TOKEN_JSON}")
OUTPUT_DIR = Path("${RAW_WIKI_OUTPUT_DIR}")
MAX_MAILS = 7
MAX_MAILS_PER_SOURCE = 4

# Keep these lists public-safe: heuristics only, not secrets.
NOISE_SENDERS = [
    "news@us.e.cos.com",
    "newsletter@mobbin.com",
    "updates-noreply@linkedin.com",
    "notifications-noreply@linkedin.com",
    "messages-noreply@linkedin.com",
    "coursera@m.learn.coursera.org",
    "support@devpost.com",
    "reply@camp.roadrunnersports.com",
    "noreply@lovable.dev",
    "no-reply@youtube.com",
    "info@n.myprotein.com",
]
NOISE_SUBJECT_KEYWORDS = [
    "up to",
    "mobile drop",
    "sale",
    "off",
    "newsletter",
    "webinar",
    "광고",
    "할인",
    "종료 임박",
]
IMPORTANT_SENDER_HINTS = [
    "github.com",
    "vercel.com",
    "naver.com",
    "snu",
    "hospital",
    "journal",
]
IMPORTANT_SUBJECT_HINTS = [
    "physio_app",
    "pr run failed",
    "failed preview deployment",
    "review requested",
    "ci",
    "deploy",
    "calendar",
    "미팅",
]
SECONDARY_PRIORITY_SENDER_HINTS = [
    "naver.com",
    "snu",
    "hospital",
    "ac.kr",
    "edu",
    "journal",
    "github.com",
    "vercel.com",
]
WEEKDAY_TODO = {
    0: "physio_app 관련 핵심 작업 1개만 전진시키기",
    1: "physio_app 관련 핵심 작업 1개만 전진시키기",
    2: "hawkeye 관련 핵심 작업 1개만 전진시키기",
    3: "visualprm 관련 핵심 작업 1개만 전진시키기",
    4: "물리치료 연구 진행 + 중요 회신 확인",
    5: "주말: 운영 backlog 정리 또는 휴식 우선",
    6: "주간 계획 재정렬 및 다음 주 준비",
}

VISIT_REHAB_CALENDAR_ID = "${VISIT_REHAB_CALENDAR_ID}"
CALENDAR_IDS = ["primary", VISIT_REHAB_CALENDAR_ID]
CALENDAR_NAME_MAP = {
    VISIT_REHAB_CALENDAR_ID: "방문재활",
    "primary": "기본",
}


def load_creds(path: Path) -> Credentials:
    data = json.loads(path.read_text())
    scopes = (data.get("scope") or "").split() or data.get("scopes")
    return Credentials.from_authorized_user_info(data, scopes=scopes)


def iso_day_bounds(day: datetime) -> tuple[str, str]:
    start = day.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)
    return start.isoformat(), end.isoformat()


def parse_event_time(event: dict[str, Any]) -> tuple[datetime | None, datetime | None, bool]:
    start_raw = event.get("start", {})
    end_raw = event.get("end", {})
    if "date" in start_raw:
        start = datetime.fromisoformat(start_raw["date"]).replace(tzinfo=KST)
        end = datetime.fromisoformat(end_raw.get("date", start_raw["date"])).replace(tzinfo=KST)
        return start, end, True
    start = datetime.fromisoformat(start_raw["dateTime"]).astimezone(KST)
    end = datetime.fromisoformat(end_raw["dateTime"]).astimezone(KST)
    return start, end, False


def is_lunch_event(summary: str) -> bool:
    s = (summary or "").lower()
    return any(k in s for k in ["점심", "런치", "lunch"])


def is_cancelled_event(event: dict[str, Any], summary: str) -> bool:
    if event.get("status") == "cancelled":
        return True
    return any(k in (summary or "").lower() for k in ["취소", "cancelled", "canceled"])


def format_event(event: dict[str, Any]) -> str | None:
    summary = (event.get("summary") or "(제목 없음)").strip()
    if is_lunch_event(summary) or is_cancelled_event(event, summary):
        return None
    start, end, all_day = parse_event_time(event)
    if not all_day and (start is None or end is None):
        return None
    cal_id = event.get("organizer", {}).get("email") or event.get("calendarId") or ""
    cal_name = CALENDAR_NAME_MAP.get(cal_id, event.get("organizer", {}).get("displayName") or "기타")
    time_text = "하루종일" if all_day else f"{start.strftime('%H:%M')}-{end.strftime('%H:%M')}"
    location = (event.get("location") or "").strip()
    loc_text = f" | {location}" if location else ""
    return f"- {time_text} | {summary} [{cal_name}]{loc_text}"


def get_calendar_items() -> tuple[list[str], list[str], list[str], list[str]]:
    issues: list[str] = []
    today_lines: list[str] = []
    tomorrow_lines: list[str] = []
    upcoming_lines: list[str] = []
    svc = build("calendar", "v3", credentials=load_creds(PRIMARY_TOKEN))
    now = datetime.now(KST)

    def fetch_events(time_min: str, time_max: str, max_results: int) -> list[dict[str, Any]]:
        merged: list[dict[str, Any]] = []
        seen: set[str] = set()
        for calendar_id in CALENDAR_IDS:
            try:
                events = svc.events().list(
                    calendarId=calendar_id,
                    timeMin=time_min,
                    timeMax=time_max,
                    singleEvents=True,
                    orderBy="startTime",
                    maxResults=max_results,
                ).execute().get("items", [])
            except Exception as e:
                issues.append(f"calendar:{calendar_id}: {type(e).__name__}: {e}")
                continue
            for event in events:
                event_key = event.get("id") or json.dumps(event.get("start", {}), sort_keys=True) + (event.get("summary") or "")
                if event_key in seen:
                    continue
                seen.add(event_key)
                event["calendarId"] = calendar_id
                merged.append(event)
        merged.sort(key=lambda e: parse_event_time(e)[0] or now)
        return merged

    for label, day in [("today", now), ("tomorrow", now + timedelta(days=1))]:
        time_min, time_max = iso_day_bounds(day)
        events = fetch_events(time_min, time_max, 50)
        formatted = [x for e in events if (x := format_event(e))]
        if label == "today":
            today_lines = formatted
        else:
            tomorrow_lines = formatted

    start_3 = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end_3 = start_3 + timedelta(days=4)
    events = fetch_events(start_3.isoformat(), end_3.isoformat(), 100)
    grouped: dict[str, list[str]] = defaultdict(list)
    for event in events:
        line = format_event(event)
        if not line:
            continue
        start, _, _ = parse_event_time(event)
        if not start:
            continue
        day_key = start.strftime("%m-%d(%a)")
        grouped[day_key].append(line[2:])
    for day_key, items in grouped.items():
        upcoming_lines.append(f"- {day_key}: " + " / ".join(items[:3]))
    return today_lines, tomorrow_lines, upcoming_lines, issues


def gmail_service(path: Path) -> tuple[Any | None, str | None]:
    try:
        svc = build("gmail", "v1", credentials=load_creds(path))
        svc.users().labels().list(userId="me").execute()
        return svc, None
    except Exception as e:
        return None, f"{path.name}: {type(e).__name__}: {e}"


def get_header_map(payload: dict[str, Any]) -> dict[str, str]:
    return {h.get("name", ""): h.get("value", "") for h in payload.get("headers", [])}


def classify_mail(source: str, headers: dict[str, str], snippet: str) -> str:
    text = " ".join([headers.get("From", ""), headers.get("Subject", ""), snippet])
    if re.search(r"naver|네이버|mail\.naver|navercorp", text, re.I):
        return "NAVER"
    return source


def is_noise_mail(headers: dict[str, Any], snippet: str) -> bool:
    text = f"{headers.get('From', '').lower()} {headers.get('Subject', '').lower()} {snippet.lower()}"
    return any(sender in text for sender in NOISE_SENDERS) or any(k in text for k in NOISE_SUBJECT_KEYWORDS)


def should_keep_secondary_mail(headers: dict[str, str], snippet: str) -> bool:
    body_text = f"{headers.get('From', '').lower()} {headers.get('Subject', '').lower()} {snippet.lower()}"
    if any(hint in body_text for hint in SECONDARY_PRIORITY_SENDER_HINTS):
        return True
    email_match = re.search(r"<([^>]+)>", headers.get("From", ""))
    sender_email = (email_match.group(1) if email_match else headers.get("From", "")).strip().lower()
    local_part = sender_email.split("@", 1)[0] if "@" in sender_email else sender_email
    if any(marker in local_part for marker in ["noreply", "no-reply", "notifications", "notification", "updates", "mailer-daemon"]):
        return False
    return "@" in sender_email


def score_mail(tag: str, headers: dict[str, Any], snippet: str, labels: set[str]) -> int:
    score = 0
    body_text = f"{headers.get('From', '').lower()} {headers.get('Subject', '').lower()} {snippet.lower()}"
    if "UNREAD" in labels:
        score += 3
    if "IMPORTANT" in labels:
        score += 2
    if tag == "NAVER":
        score += 2
    if any(hint in body_text for hint in IMPORTANT_SENDER_HINTS):
        score += 3
    if any(hint in body_text for hint in IMPORTANT_SUBJECT_HINTS):
        score += 4
    if any(hint in body_text for hint in NOISE_SUBJECT_KEYWORDS):
        score -= 6
    return score


def compact_devops_mails(scored_items: list[dict[str, Any]], source: str) -> list[str]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    direct_lines: list[str] = []
    for item in scored_items:
        sender = item["from_text"]
        subject = item["subject"]
        if "github.com" in sender and "physio_app" in subject.lower():
            if "pr run failed" in subject.lower() or "run failed" in subject.lower():
                grouped["github_ci_failures"].append(item)
            else:
                grouped["github_pr_updates"].append(item)
        elif "vercel.com" in sender:
            grouped["vercel_alerts"].append(item)
        else:
            direct_lines.append(item["line"])

    compacted: list[str] = []
    if grouped["github_ci_failures"]:
        repos = Counter()
        for item in grouped["github_ci_failures"]:
            m = re.search(r"\[([^/]+/[^\]]+)\]", item["subject"])
            repos[m.group(1) if m else "repo-unknown"] += 1
        compacted.append(
            f"- [{source}] GitHub CI 실패 {len(grouped['github_ci_failures'])}건 | "
            + ", ".join(f"{repo} {count}건" for repo, count in repos.most_common(2))
        )
    if grouped["github_pr_updates"]:
        compacted.append(f"- [{source}] physio_app 관련 GitHub PR 업데이트 {len(grouped['github_pr_updates'])}건")
    if grouped["vercel_alerts"]:
        compacted.append(f"- [{source}] Vercel 배포 알림 {len(grouped['vercel_alerts'])}건")
    compacted.extend(direct_lines)
    return compacted[:MAX_MAILS_PER_SOURCE]


def source_query(source: str) -> str:
    if source == "B":
        return "newer_than:7d (is:important OR is:unread OR in:inbox OR category:primary)"
    return "newer_than:1d -(category:promotions) (is:important OR is:unread OR category:primary)"


def collect_messages() -> tuple[list[str], list[str]]:
    issues: list[str] = []
    mail_lines: list[str] = []
    for source, path in [("A", PRIMARY_TOKEN), ("B", SECONDARY_TOKEN)]:
        scored_items: list[dict[str, Any]] = []
        svc, err = gmail_service(path)
        if err:
            issues.append(err)
            continue
        result = svc.users().messages().list(userId="me", q=source_query(source), maxResults=10).execute()
        for item in result.get("messages", []):
            msg = svc.users().messages().get(
                userId="me",
                id=item["id"],
                format="metadata",
                metadataHeaders=["From", "Subject", "Date"],
            ).execute()
            headers = get_header_map(msg.get("payload", {}))
            labels = set(msg.get("labelIds", []))
            snippet = msg.get("snippet", "")
            tag = classify_mail(source, headers, snippet)
            if is_noise_mail(headers, snippet):
                continue
            if source == "B" and not should_keep_secondary_mail(headers, snippet):
                continue
            score = score_mail(tag, headers, snippet, labels)
            if score <= 0:
                continue
            scored_items.append({
                "score": score,
                "line": f"- [{tag}] {headers.get('Subject', '(제목 없음)')} | {headers.get('From', '')[:50]}",
                "subject": headers.get("Subject", "(제목 없음)"),
                "from_text": headers.get("From", "").lower(),
            })
        scored_items.sort(key=lambda x: x["score"], reverse=True)
        source_lines = compact_devops_mails(scored_items, source)
        label = "A 계정(Primary)" if source == "A" else "B 계정(Secondary)"
        mail_lines.append(f"- {label}")
        mail_lines.extend([f"  {line}" for line in source_lines] or ["  - 표시할 중요 메일 없음"])
    return mail_lines[: MAX_MAILS + 4], issues


def priority_actions(today_events: list[str], mails: list[str], issues: list[str]) -> list[str]:
    actions = []
    if issues:
        actions.append("P1. 캘린더/메일 일부 소스 인증 또는 연결 상태 점검")
    if mails:
        actions.append("P2. 중요/미읽음 메일 상위 2건 먼저 처리")
    actions.append("P3. " + WEEKDAY_TODO[datetime.now(KST).weekday()])
    return actions[:3]


def section(title: str, lines: list[str], fallback: str = "- 없음") -> list[str]:
    return [title] + (lines if lines else [fallback]) + [""]


def main() -> None:
    now = datetime.now(KST)
    date_str = now.strftime("%Y-%m-%d")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    today_lines, tomorrow_lines, upcoming_lines, cal_issues = get_calendar_items()
    mail_lines, mail_issues = collect_messages()
    issues = cal_issues + mail_issues
    todo_line = "- " + WEEKDAY_TODO[now.weekday()]
    actions = [f"- {x}" for x in priority_actions(today_lines, mail_lines, issues)]

    body: list[str] = []
    body.append(f"# 아침 브리핑 | {date_str} (KST)")
    body.append("")
    body.extend(section("## 1) 오늘 일정", today_lines))
    body.extend(section("## 2) 내일 일정", tomorrow_lines))
    body.extend(section("## 3) 3일 내 주요 일정", upcoming_lines))
    body.extend(section("## 4) 최근 24시간 중요/미읽음 메일", mail_lines))
    body.extend(section("## 5) 오늘의 할 일", [todo_line]))
    body.extend(section("## 6) 우선순위 액션", actions))
    if issues:
        body.extend(section("## 참고: 수집 이슈", [f"- {x}" for x in issues]))

    out_path = OUTPUT_DIR / f"{date_str}.md"
    out_path.write_text("\n".join(body).strip() + "\n", encoding="utf-8")
    print(f"저장한 브리핑 파일: {out_path}")
    print("핵심 요약:")
    print(today_lines[0] if today_lines else "- 오늘 일정 없음")
    print(mail_lines[0] if mail_lines else "- 중요/미읽음 메일 없음")
    print(actions[0] if actions else "- 우선순위 액션 없음")


if __name__ == "__main__":
    main()
