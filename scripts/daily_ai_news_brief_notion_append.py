#!/usr/bin/env python3
import argparse
import json
import os
import sys
import urllib.request
from pathlib import Path
from typing import Any

NOTION_VERSION = "2025-09-03"
DEFAULT_DATA_SOURCE_ID = "3755935a-1522-817e-a12f-000b844ba448"  # AI News Briefings DB (2026 Q2)
ENV_CANDIDATES = [
    "/home/yk/.hermes/.env",
    "/home/yk/.openclaw/workspace/Hawkeye/.env",
]


def q(v: Any) -> str:
    if v is None:
        return ""
    return str(v).strip()


def norm(s: str) -> str:
    return " ".join(q(s).lower().split())


def split_multi(value: Any) -> list[str]:
    if isinstance(value, list):
        return [q(v) for v in value if q(v)]
    text = q(value)
    if not text:
        return []
    return [part.strip() for part in text.replace(";", ",").split(",") if part.strip()]


def load_env() -> None:
    for env_path in ENV_CANDIDATES:
        path = Path(env_path)
        if not path.exists():
            continue
        for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            if "=" not in raw or raw.lstrip().startswith("#"):
                continue
            key, value = raw.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def load_token() -> str:
    load_env()
    token = os.getenv("NOTION_TOKEN") or os.getenv("NOTION_API_KEY")
    if token:
        return token
    raise SystemExit("NOTION token not found in Hermes env or legacy fallback env")


def get_data_source_id() -> str:
    return q(os.getenv("NOTION_AI_NEWS_BRIEFINGS_DATA_SOURCE_ID") or DEFAULT_DATA_SOURCE_ID)


def notion_request(path: str, token: str, method: str = "GET", payload: dict[str, Any] | None = None) -> dict[str, Any]:
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        f"https://api.notion.com/v1{path}",
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Notion-Version": NOTION_VERSION,
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def read_items(path: str | None) -> list[dict[str, Any]]:
    text = Path(path).read_text(encoding="utf-8") if path else sys.stdin.read()
    data = json.loads(text)
    if not isinstance(data, list):
        raise SystemExit("Input must be a JSON array")
    return data


def fetch_existing_index(data_source_id: str, token: str) -> tuple[set[str], set[str], int]:
    urls: set[str] = set()
    titles: set[str] = set()
    total = 0
    cursor = None
    while True:
        payload: dict[str, Any] = {"page_size": 100}
        if cursor:
            payload["start_cursor"] = cursor
        data = notion_request(f"/data_sources/{data_source_id}/query", token, method="POST", payload=payload)
        for row in data.get("results", []):
            total += 1
            props = row.get("properties", {})
            url = (props.get("URL") or {}).get("url")
            if url:
                urls.add(q(url))
            title_parts = ((props.get("Name") or {}).get("title") or [])
            title = "".join(part.get("plain_text", "") for part in title_parts).strip()
            if title:
                titles.add(norm(title))
        if not data.get("has_more"):
            break
        cursor = data.get("next_cursor")
    return urls, titles, total


def build_properties(item: dict[str, Any]) -> dict[str, Any]:
    topics = split_multi(item.get("topics") or item.get("topic_tags") or item.get("topic"))
    if not topics:
        topics = ["agents"]
    return {
        "Name": {"title": [{"text": {"content": q(item.get("title"))[:1900]}}]},
        "Date": {"date": {"start": q(item.get("date"))}},
        "Source": {"select": {"name": q(item.get("source")) or "Other"}},
        "Type": {"select": {"name": q(item.get("type")) or "briefing"}},
        "Topic": {"multi_select": [{"name": topic[:100]} for topic in topics[:10]]},
        "Insight": {"rich_text": [{"text": {"content": q(item.get("insight"))[:1900]}}]},
        "URL": {"url": q(item.get("url"))},
        "Priority": {"select": {"name": q(item.get("priority")) or "medium"}},
        "Status": {"select": {"name": q(item.get("status")) or "new"}},
        "Week": {"rich_text": [{"text": {"content": q(item.get("week"))[:1900]}}]},
    }


def validate_item(item: dict[str, Any]) -> list[str]:
    required = ["title", "date", "url", "insight"]
    return [field for field in required if not q(item.get(field))]


def main() -> int:
    parser = argparse.ArgumentParser(description="Append daily AI news briefing rows into Notion")
    parser.add_argument("--input", help="Path to JSON array input. Defaults to stdin")
    args = parser.parse_args()

    token = load_token()
    data_source_id = get_data_source_id()
    items = read_items(args.input)
    existing_urls, existing_titles, before_count = fetch_existing_index(data_source_id, token)

    inserted = 0
    skipped_duplicates = 0
    skipped_invalid = 0
    inserted_titles: list[str] = []
    invalid_details: list[dict[str, Any]] = []
    duplicate_titles: list[str] = []

    for item in items:
        title = q(item.get("title"))
        url = q(item.get("url"))
        missing = validate_item(item)
        if missing:
            skipped_invalid += 1
            invalid_details.append({"title": title or "(untitled)", "missing": missing})
            continue
        if url in existing_urls or norm(title) in existing_titles:
            skipped_duplicates += 1
            duplicate_titles.append(title)
            continue
        payload = {
            "parent": {"data_source_id": data_source_id},
            "properties": build_properties(item),
        }
        notion_request("/pages", token, method="POST", payload=payload)
        inserted += 1
        inserted_titles.append(title)
        existing_urls.add(url)
        existing_titles.add(norm(title))

    result = {
        "data_source_id": data_source_id,
        "input_count": len(items),
        "inserted": inserted,
        "skipped_duplicates": skipped_duplicates,
        "skipped_invalid": skipped_invalid,
        "before_count": before_count,
        "after_count": before_count + inserted,
        "inserted_titles": inserted_titles,
        "duplicate_titles": duplicate_titles,
        "invalid_details": invalid_details,
    }
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
