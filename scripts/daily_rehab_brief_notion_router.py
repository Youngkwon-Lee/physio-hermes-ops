#!/usr/bin/env python3
import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

NOTION_VERSION = "2025-09-03"
DEFAULT_DB_IDS = {
    "paper": "3395935a-1522-81aa-b892-f88ac923d589",    # 논문/연구 DB (2026 Q2)
    "dataset": "3395935a-1522-8126-abef-dc19f794a572",  # Dataset/Benchmark DB (2026 Q2)
    "startup": "3395935a-1522-8136-85ac-c80185b3fd60",  # Startups/Industry DB (2026 Q2)
}
DEFAULT_DATA_SOURCE_IDS = {
    "paper": "3395935a-1522-8154-952d-000b68f7fdd8",    # 논문/연구 DB (2026 Q2)
    "dataset": "3395935a-1522-81ae-9268-000b5a584a6d",  # Dataset/Benchmark DB (2026 Q2)
    "startup": "3395935a-1522-8165-ab3e-000b6200d571",  # Startups/Industry DB (2026 Q2)
}
ENV_CANDIDATES = [
    "/home/yk/.hermes/.env",
    "/home/yk/.openclaw/workspace/Hawkeye/.env",
]

PAPER_TYPES = {"paper", "논문", "research", "연구", "research_trend", "연구동향"}
DATASET_TYPES = {"dataset", "benchmark", "데이터셋", "벤치마크"}
STARTUP_TYPES = {"startup", "company", "industry", "product", "funding", "기업", "산업", "제품", "스타트업"}


def q(v: Any) -> str:
    if v is None:
        return ""
    return str(v).strip()


def norm(s: str) -> str:
    return " ".join(q(s).lower().split())


def split_multi(value: Any, default: list[str] | None = None) -> list[str]:
    if isinstance(value, list):
        items = [q(v) for v in value if q(v)]
    else:
        text = q(value)
        items = [part.strip() for part in text.replace(";", ",").split(",") if part.strip()] if text else []
    return items or (default or [])


def parse_optional_float(value: Any, default: float = 0.0) -> float:
    text = q(value)
    if not text:
        return default
    normalized = text.replace(",", "").strip().lower()
    if normalized in {"n/a", "na", "none", "null", "-", "--", "unknown"}:
        return default
    try:
        return float(normalized)
    except ValueError:
        return default


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


def get_db_id(kind: str) -> str:
    mapping = {
        "paper": os.getenv("NOTION_REHAB_Q2_DB_ID") or os.getenv("NOTION_PAPER_Q2_DB_ID") or DEFAULT_DB_IDS["paper"],
        "dataset": os.getenv("NOTION_DATASET_Q2_DB_ID") or DEFAULT_DB_IDS["dataset"],
        "startup": os.getenv("NOTION_STARTUP_Q2_DB_ID") or DEFAULT_DB_IDS["startup"],
    }
    return q(mapping[kind])


def get_data_source_id(kind: str) -> str:
    mapping = {
        "paper": os.getenv("NOTION_REHAB_Q2_DATA_SOURCE_ID") or os.getenv("NOTION_PAPER_Q2_DATA_SOURCE_ID") or DEFAULT_DATA_SOURCE_IDS["paper"],
        "dataset": os.getenv("NOTION_DATASET_Q2_DATA_SOURCE_ID") or DEFAULT_DATA_SOURCE_IDS["dataset"],
        "startup": os.getenv("NOTION_STARTUP_Q2_DATA_SOURCE_ID") or DEFAULT_DATA_SOURCE_IDS["startup"],
    }
    return q(mapping[kind])


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
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))


def read_items(path: str | None) -> list[dict[str, Any]]:
    text = Path(path).read_text(encoding="utf-8") if path else sys.stdin.read()
    data = json.loads(text)
    if not isinstance(data, list):
        raise SystemExit("Input must be a JSON array")
    return data


def classify_kind(item: dict[str, Any]) -> str:
    raw = norm(q(item.get("item_type") or item.get("type") or item.get("category_type")))
    if raw in PAPER_TYPES:
        return "paper"
    if raw in DATASET_TYPES:
        return "dataset"
    if raw in STARTUP_TYPES:
        return "startup"

    category = norm(q(item.get("category")))
    if any(word in category for word in ["dataset", "benchmark", "데이터셋", "벤치마크"]):
        return "dataset"
    if any(word in category for word in ["startup", "company", "product", "industry", "기업", "제품", "스타트업"]):
        return "startup"
    return "paper"


def fetch_existing_index(data_source_id: str, token: str, title_key: str) -> tuple[set[str], set[str], int]:
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
            url = ((props.get("링크") or {}).get("url"))
            if url:
                urls.add(q(url))
            title_parts = ((props.get(title_key) or {}).get("title") or [])
            title = "".join(part.get("plain_text", "") for part in title_parts).strip()
            if title:
                titles.add(norm(title))
            if row.get("archived"):
                archived_url = q(url)
                if archived_url:
                    urls.add(archived_url)
                if title:
                    titles.add(norm(title))
        if not data.get("has_more"):
            break
        cursor = data.get("next_cursor")
    return urls, titles, total


def build_paper_properties(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "제목": {"title": [{"text": {"content": q(item.get("title"))[:1900]}}]},
        "저널": {"rich_text": [{"text": {"content": q(item.get("journal"))[:1900]}}]},
        "저자": {"rich_text": [{"text": {"content": (q(item.get("authors") or item.get("author")) or "N/A")[:1900]}}]},
        "출처": {"select": {"name": q(item.get("source")) or "PubMed"}},
        "링크": {"url": q(item.get("url"))},
        "발행일": {"date": {"start": q(item.get("published") or item.get("date"))}},
        "요약": {"rich_text": [{"text": {"content": q(item.get("summary"))[:1900]}}]},
        "핵심기여(1문장)": {"rich_text": [{"text": {"content": q(item.get("contribution"))[:1900]}}]},
        "IF": {"number": parse_optional_float(item.get("if"), 0.0)},
        "분기": {"select": {"name": q(item.get("quarter")) or "2026Q2"}},
        "카테고리": {"select": {"name": q(item.get("category")) or "논문/연구"}},
        "근거수준": {"select": {"name": q(item.get("evidence")) or "리뷰"}},
    }


def build_dataset_properties(item: dict[str, Any]) -> dict[str, Any]:
    tags = split_multi(item.get("tags"), default=["rehab-ai"])
    return {
        "데이터셋/벤치마크명": {"title": [{"text": {"content": q(item.get("title"))[:1900]}}]},
        "출처/기관": {"rich_text": [{"text": {"content": (q(item.get("org")) or q(item.get("source_org")) or q(item.get("journal")) or "N/A")[:1900]}}]},
        "공개일": {"date": {"start": q(item.get("published") or item.get("date"))}},
        "링크": {"url": q(item.get("url"))},
        "요약": {"rich_text": [{"text": {"content": q(item.get("summary"))[:1900]}}]},
        "핵심기여(1문장)": {"rich_text": [{"text": {"content": q(item.get("contribution"))[:1900]}}]},
        "분기": {"select": {"name": q(item.get("quarter")) or "2026Q2"}},
        "카테고리": {"select": {"name": q(item.get("category")) or "재활/로보틱스"}},
        "유형": {"select": {"name": q(item.get("dataset_type") or item.get("subtype")) or "dataset"}},
        "활용난이도": {"select": {"name": q(item.get("difficulty")) or "medium"}},
        "태그": {"multi_select": [{"name": tag[:100]} for tag in tags[:10]]},
    }


def build_startup_properties(item: dict[str, Any]) -> dict[str, Any]:
    areas = split_multi(item.get("application_area") or item.get("areas") or item.get("tags"), default=["rehab-ai"])
    return {
        "항목명": {"title": [{"text": {"content": q(item.get("title"))[:1900]}}]},
        "회사/기관": {"rich_text": [{"text": {"content": (q(item.get("org")) or q(item.get("company")) or q(item.get("journal")) or "N/A")[:1900]}}]},
        "날짜": {"date": {"start": q(item.get("published") or item.get("date"))}},
        "링크": {"url": q(item.get("url"))},
        "요약": {"rich_text": [{"text": {"content": q(item.get("summary"))[:1900]}}]},
        "핵심기여(1문장)": {"rich_text": [{"text": {"content": q(item.get("contribution"))[:1900]}}]},
        "분기": {"select": {"name": q(item.get("quarter")) or "2026Q2"}},
        "카테고리": {"select": {"name": q(item.get("category")) or "재활 AI"}},
        "유형": {"select": {"name": q(item.get("startup_type") or item.get("subtype") or item.get("type")) or "startup"}},
        "영향도": {"select": {"name": q(item.get("impact")) or "medium"}},
        "적용영역": {"multi_select": [{"name": area[:100]} for area in areas[:10]]},
    }


def validate_item(item: dict[str, Any], kind: str) -> list[str]:
    required = ["title", "url", "summary", "contribution"]
    if kind == "paper":
        required += ["journal", "published"]
    else:
        required += ["published"]
    return [field for field in required if not q(item.get(field))]


def create_page(db_id: str, token: str, properties: dict[str, Any]) -> dict[str, Any]:
    payload = {"parent": {"database_id": db_id}, "properties": properties}
    return notion_request("/pages", token, method="POST", payload=payload)


def main() -> None:
    parser = argparse.ArgumentParser(description="Route daily rehab brief items to the proper Notion Q2 DB")
    parser.add_argument("--input", help="Path to JSON array file. If omitted, read stdin.")
    args = parser.parse_args()

    token = load_token()
    items = read_items(args.input)
    indexes = {
        "paper": fetch_existing_index(get_data_source_id("paper"), token, "제목"),
        "dataset": fetch_existing_index(get_data_source_id("dataset"), token, "데이터셋/벤치마크명"),
        "startup": fetch_existing_index(get_data_source_id("startup"), token, "항목명"),
    }
    existing_urls = {k: v[0] for k, v in indexes.items()}
    existing_titles = {k: v[1] for k, v in indexes.items()}
    before_count = {k: v[2] for k, v in indexes.items()}

    inserted: list[dict[str, Any]] = []
    skipped_duplicates: list[dict[str, Any]] = []
    skipped_invalid: list[dict[str, Any]] = []

    for item in items:
        kind = classify_kind(item)
        title = q(item.get("title"))
        url = q(item.get("url"))
        missing = validate_item(item, kind)
        if missing:
            skipped_invalid.append({"kind": kind, "title": title, "url": url, "missing": missing})
            continue
        title_norm = norm(title)
        if url in existing_urls[kind] or title_norm in existing_titles[kind]:
            skipped_duplicates.append({"kind": kind, "title": title, "url": url})
            continue
        props = {
            "paper": build_paper_properties,
            "dataset": build_dataset_properties,
            "startup": build_startup_properties,
        }[kind](item)
        try:
            out = create_page(get_db_id(kind), token, props)
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="ignore")
            raise SystemExit(f"Notion write failed for {kind}:{title}: HTTP {exc.code} {body}") from exc
        inserted.append({"kind": kind, "title": title, "url": url, "id": out.get("id")})
        existing_urls[kind].add(url)
        existing_titles[kind].add(title_norm)

    print(json.dumps({
        "ok": True,
        "db_ids": {k: get_db_id(k) for k in ["paper", "dataset", "startup"]},
        "before_count": before_count,
        "after_count": {k: before_count[k] + sum(1 for row in inserted if row["kind"] == k) for k in before_count},
        "inserted": inserted,
        "skipped_duplicates": skipped_duplicates,
        "skipped_invalid": skipped_invalid,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
