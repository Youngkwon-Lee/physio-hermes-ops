#!/usr/bin/env python3
import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

NOTION_VERSION = "2025-09-03"
DEFAULT_DATA_SOURCE_ID = "3755935a-1522-817e-a12f-000b844ba448"  # AI News Briefings DB (2026 Q2)
ENV_CANDIDATES = [
    "/home/yk/.hermes/.env",
    "/home/yk/.openclaw/workspace/Hawkeye/.env",
]

SOURCE_ALIASES = {
    "openai": "OpenAI Blog",
    "openai blog": "OpenAI Blog",
    "google": "Google",
    "google deepmind": "Google DeepMind",
    "anthropic": "Anthropic",
    "xai": "xAI",
    "meta": "Meta",
    "mistral": "Mistral",
    "microsoft": "Microsoft",
    "nvidia": "NVIDIA",
}

TYPE_ALIASES = {
    "infra": "infrastructure",
    "infrastructure": "infrastructure",
    "model release / infra": "infrastructure",
    "product/infra": "Product/Infrastructure",
    "product/infrastructure": "Product/Infrastructure",
    "product/api": "Product/API",
    "product/release": "product/release",
    "product/preview": "product/preview",
    "briefing": "briefing",
    "news": "news",
    "agent": "agent",
    "api": "api",
    "product": "product",
    "research": "research",
}


def q(v: Any) -> str:
    if v is None:
        return ""
    return str(v).strip()


def norm(s: str) -> str:
    return " ".join(q(s).lower().split())


def to_int(v: Any, default: int) -> int:
    try:
        if v is None or q(v) == "":
            return default
        return int(v)
    except (TypeError, ValueError):
        return default


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


def get_data_source(data_source_id: str, token: str) -> dict[str, Any]:
    return notion_request(f"/data_sources/{data_source_id}", token)


def get_database_id(data_source: dict[str, Any]) -> str:
    parent = data_source.get("parent") or {}
    database_id = q(parent.get("database_id"))
    if not database_id:
        raise SystemExit(f"database_id not found for data source {q(data_source.get('id'))}")
    return database_id


def read_items(path: str | None) -> list[dict[str, Any]]:
    text = Path(path).read_text(encoding="utf-8") if path else sys.stdin.read()
    data = json.loads(text)
    if not isinstance(data, list):
        raise SystemExit("Input must be a JSON array")
    return data


def extract_row_summary(row: dict[str, Any]) -> dict[str, str]:
    props = row.get("properties", {})
    title_parts = ((props.get("Name") or {}).get("title") or [])
    title = "".join(part.get("plain_text", "") for part in title_parts).strip()
    url = q((props.get("URL") or {}).get("url"))
    return {
        "id": q(row.get("id")),
        "page_url": q(row.get("url")),
        "created_time": q(row.get("created_time")),
        "title": title,
        "url": url,
    }


def query_rows_by_url(data_source_id: str, token: str, url: str) -> list[dict[str, str]]:
    payload = {"filter": {"property": "URL", "url": {"equals": url}}}
    data = notion_request(f"/data_sources/{data_source_id}/query", token, method="POST", payload=payload)
    return [extract_row_summary(row) for row in data.get("results", [])]


def count_existing_rows(data_source_id: str, token: str) -> int:
    total = 0
    cursor = None
    while True:
        payload: dict[str, Any] = {"page_size": 100}
        if cursor:
            payload["start_cursor"] = cursor
        data = notion_request(f"/data_sources/{data_source_id}/query", token, method="POST", payload=payload)
        total += len(data.get("results", []))
        if not data.get("has_more"):
            break
        cursor = data.get("next_cursor")
    return total


def property_option_names(data_source: dict[str, Any], property_name: str) -> set[str]:
    prop = (data_source.get("properties") or {}).get(property_name) or {}
    prop_type = q(prop.get("type"))
    config = prop.get(prop_type) or {}
    return {q(opt.get("name")) for opt in config.get("options", []) if q(opt.get("name"))}


def canonical_source(value: Any, allowed: set[str]) -> str:
    raw = q(value)
    if raw in allowed:
        return raw
    lowered = norm(raw)
    candidate = SOURCE_ALIASES.get(lowered)
    if candidate and candidate in allowed:
        return candidate
    for option in allowed:
        if lowered and lowered in norm(option):
            return option
    return "Other" if "Other" in allowed else (raw or "Other")


def canonical_type(value: Any, allowed: set[str]) -> str:
    raw = q(value)
    if raw in allowed:
        return raw
    lowered = norm(raw)
    candidate = TYPE_ALIASES.get(lowered)
    if candidate and candidate in allowed:
        return candidate
    for option in allowed:
        if lowered and (lowered == norm(option) or lowered in norm(option) or norm(option) in lowered):
            return option
    return "briefing" if "briefing" in allowed else (raw or "briefing")


def canonical_priority(value: Any, allowed: set[str]) -> str:
    raw = q(value)
    if raw in allowed:
        return raw
    score = to_int(value, -1)
    if score >= 0:
        numeric = str(score)
        if numeric in allowed:
            return numeric
        if score >= 7 and "high" in allowed:
            return "high"
        if score >= 4 and "medium" in allowed:
            return "medium"
        if "low" in allowed:
            return "low"
    lowered = norm(raw)
    if lowered in {"high", "medium", "low"} and lowered in allowed:
        return lowered
    return "medium" if "medium" in allowed else (raw or "medium")


def canonical_topics(value: Any) -> list[str]:
    topics = split_multi(value)
    normalized: list[str] = []
    seen: set[str] = set()
    for topic in topics:
        cleaned = q(topic)[:100]
        if not cleaned:
            continue
        key = norm(cleaned)
        if key in seen:
            continue
        seen.add(key)
        normalized.append(cleaned)
    return normalized or ["agents"]


def build_properties(item: dict[str, Any], data_source: dict[str, Any]) -> dict[str, Any]:
    source_options = property_option_names(data_source, "Source")
    type_options = property_option_names(data_source, "Type")
    priority_options = property_option_names(data_source, "Priority")
    topics = canonical_topics(item.get("topics") or item.get("topic_tags") or item.get("topic"))
    return {
        "Name": {"title": [{"text": {"content": q(item.get("title"))[:1900]}}]},
        "Date": {"date": {"start": q(item.get("date"))}},
        "Source": {"select": {"name": canonical_source(item.get("source"), source_options)}},
        "Type": {"select": {"name": canonical_type(item.get("type"), type_options)}},
        "Topic": {"multi_select": [{"name": topic} for topic in topics[:10]]},
        "Insight": {"rich_text": [{"text": {"content": q(item.get("insight"))[:1900]}}]},
        "URL": {"url": q(item.get("url"))},
        "Priority": {"select": {"name": canonical_priority(item.get("priority"), priority_options)}},
        "Status": {"select": {"name": q(item.get("status")) or "new"}},
        "Week": {"rich_text": [{"text": {"content": str(to_int(item.get("week"), 0))[:1900]}}]},
    }


def fetch_url_status(url: str) -> tuple[int | None, str, str]:
    if not url.startswith(("http://", "https://")):
        return None, url, "url_not_http"
    headers = {"User-Agent": "Mozilla/5.0 (Kinelo Ops automation verifier)"}
    for method in ["HEAD", "GET"]:
        try:
            req = urllib.request.Request(url, method=method, headers=headers)
            with urllib.request.urlopen(req, timeout=15) as resp:
                body = ""
                if method == "GET":
                    body = resp.read(256_000).decode("utf-8", errors="ignore")
                return int(resp.status), resp.geturl(), body
        except urllib.error.HTTPError as error:
            if method == "GET" or error.code >= 400:
                return int(error.code), url, error.read().decode("utf-8", errors="ignore")
        except Exception as error:
            if method == "GET":
                return None, url, f"{type(error).__name__}: {error}"
    return None, url, "unknown_url_error"


def fetch_url_body(url: str) -> str:
    headers = {"User-Agent": "Mozilla/5.0 (Kinelo Ops automation verifier)"}
    req = urllib.request.Request(url, method="GET", headers=headers)
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.read(256_000).decode("utf-8", errors="ignore")


def extract_arxiv_title(html: str) -> str:
    match = re.search(r'<h1[^>]*class="title[^>]*>\s*<span[^>]*>Title:\s*</span>\s*(.*?)\s*</h1>', html, re.I | re.S)
    if not match:
        return ""
    title = re.sub(r"<[^>]+>", " ", match.group(1))
    return " ".join(title.split())


def validate_source_url(item: dict[str, Any]) -> list[str]:
    url = q(item.get("url"))
    title = q(item.get("title"))
    if not url:
        return []
    status, final_url, body = fetch_url_status(url)
    if status is None:
        return [f"url_unverified:{url}:{body[:120]}"]
    if status >= 400:
        return [f"url_unreachable:{status}:{url}"]
    parsed = urllib.parse.urlparse(final_url or url)
    if parsed.netloc.lower().endswith("arxiv.org") and parsed.path.startswith("/abs/"):
        if not body:
            try:
                body = fetch_url_body(final_url or url)
            except Exception as error:
                return [f"url_unverified:{url}:{type(error).__name__}: {error}"]
        actual_title = extract_arxiv_title(body)
        if actual_title and title and norm(title) not in norm(actual_title) and norm(actual_title) not in norm(title):
            return [f"url_title_mismatch: expected={title[:80]} actual={actual_title[:80]}"]
    return []


def validate_item(item: dict[str, Any]) -> list[str]:
    required = ["title", "date", "url", "insight"]
    errors = [field for field in required if not q(item.get(field))]
    if errors:
        return errors
    return validate_source_url(item)


def print_human_summary(result: dict[str, Any], dry_run: bool) -> None:
    mode = "DRY-RUN" if dry_run else "WRITE"
    before = result.get("before_count")
    after = result.get("after_count")
    before_text = "unknown" if before is None else str(before)
    after_text = "unknown" if after is None else str(after)
    print(
        f"[{mode}] input={result['input_count']} inserted={result['inserted']} "
        f"duplicates={result['skipped_duplicates']} invalid={result['skipped_invalid']} "
        f"before={before_text} after={after_text}"
    )
    for row in result.get("inserted_details", [])[:5]:
        print(f"  + {row['title']} -> {row['page_url']}")
    for row in result.get("duplicate_details", [])[:5]:
        existing = row.get("existing") or {}
        page_url = existing.get("page_url") or ""
        print(f"  = {row['title']} -> {page_url}")
    for row in result.get("invalid_details", [])[:5]:
        print(f"  ! {row['title']} missing={','.join(row['missing'])}")
    print(json.dumps(result, ensure_ascii=False))


def main() -> int:
    parser = argparse.ArgumentParser(description="Append daily AI news briefing rows into Notion")
    parser.add_argument("--input", help="Path to JSON array input. Defaults to stdin")
    parser.add_argument("--dry-run", action="store_true", help="Validate and dedupe without writing to Notion")
    parser.add_argument("--json-only", action="store_true", help="Print JSON only")
    parser.add_argument("--with-counts", action="store_true", help="Also compute before/after row counts via full data source scan")
    args = parser.parse_args()

    token = load_token()
    data_source_id = get_data_source_id()
    data_source = get_data_source(data_source_id, token)
    database_id = get_database_id(data_source)
    items = read_items(args.input)

    inserted = 0
    skipped_duplicates = 0
    skipped_invalid = 0
    inserted_titles: list[str] = []
    inserted_details: list[dict[str, Any]] = []
    invalid_details: list[dict[str, Any]] = []
    duplicate_titles: list[str] = []
    duplicate_details: list[dict[str, Any]] = []
    seen_input_urls: set[str] = set()

    before_count = count_existing_rows(data_source_id, token) if args.with_counts else None

    for item in items:
        title = q(item.get("title"))
        url = q(item.get("url"))
        missing = validate_item(item)
        if missing:
            skipped_invalid += 1
            invalid_details.append({"title": title or "(untitled)", "missing": missing})
            continue
        if url in seen_input_urls:
            skipped_duplicates += 1
            duplicate_titles.append(title)
            duplicate_details.append({
                "title": title,
                "url": url,
                "existing": {"title": "duplicate within input batch"},
            })
            continue

        existing_matches = query_rows_by_url(data_source_id, token, url)
        if existing_matches:
            skipped_duplicates += 1
            duplicate_titles.append(title)
            duplicate_details.append({
                "title": title,
                "url": url,
                "existing": existing_matches[0],
                "match_count": len(existing_matches),
            })
            seen_input_urls.add(url)
            continue

        properties = build_properties(item, data_source)
        if args.dry_run:
            inserted += 1
            inserted_titles.append(title)
            inserted_details.append({
                "title": title,
                "url": url,
                "page_url": "",
                "created_time": "",
                "dry_run": True,
                "properties": properties,
            })
            seen_input_urls.add(url)
            continue

        payload = {
            "parent": {"type": "data_source_id", "data_source_id": data_source_id},
            "properties": properties,
        }
        created = notion_request("/pages", token, method="POST", payload=payload)
        row_summary = extract_row_summary(created)
        inserted += 1
        inserted_titles.append(title)
        inserted_details.append(row_summary)
        seen_input_urls.add(url)

    after_count = None if before_count is None else before_count + inserted
    result = {
        "data_source_id": data_source_id,
        "database_id": database_id,
        "input_count": len(items),
        "inserted": inserted,
        "skipped_duplicates": skipped_duplicates,
        "skipped_invalid": skipped_invalid,
        "dry_run": args.dry_run,
        "before_count": before_count,
        "after_count": after_count,
        "inserted_titles": inserted_titles,
        "inserted_details": inserted_details,
        "duplicate_titles": duplicate_titles,
        "duplicate_details": duplicate_details,
        "invalid_details": invalid_details,
    }

    if args.json_only:
        print(json.dumps(result, ensure_ascii=False))
    else:
        print_human_summary(result, args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
