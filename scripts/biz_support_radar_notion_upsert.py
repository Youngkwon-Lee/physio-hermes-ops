#!/usr/bin/env python3
import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

NOTION_VERSION = '2025-09-03'
DEFAULT_DATA_SOURCE_ID = '33a5935a-1522-815b-b885-000bd9139692'
ENV_CANDIDATES = [
    '/home/yk/.hermes/.env',
    '/home/yk/.openclaw/workspace/Hawkeye/.env',
]

TITLE_PROP = '공고명'
ORG_PROP = '기관'
DEADLINE_PROP = '접수마감'
START_DATE_PROP = '접수시작'
URL_PROP = '링크'
SUMMARY_PROP = '원문요약'
FIT_PROP = '적합도'
STATUS_PROP = '상태'
FIELDS_PROP = '분야'
PROGRAM_TYPES_PROP = '사업유형'
TARGETS_PROP = '지원대상'
BENEFIT_PROP = '지원금/혜택'
REGION_PROP = '지역'
BUSINESS_REQUIRED_PROP = '사업자필요'

VALID_FIT = {'S', 'A', 'B', 'C'}
VALID_STATUS = {'신규', '검토중', '지원준비', '제출완료', '보류', '마감', '마감임박'}
VALID_REGION = {'전국', '서울', '부산', '기타', '경기', '강원'}
VALID_BIZ_REQUIRED = {'필요', '불필요', '조건부'}


def q(value: Any) -> str:
    if value is None:
        return ''
    return str(value).strip()


def norm(value: Any) -> str:
    return ' '.join(q(value).lower().split())


def split_multi(value: Any) -> list[str]:
    if isinstance(value, list):
        return [q(v) for v in value if q(v)]
    text = q(value)
    if not text:
        return []
    return [part.strip() for part in text.replace(';', ',').split(',') if part.strip()]


def clamp_text(value: Any, limit: int = 1900) -> str:
    return q(value)[:limit]


def rich_text_value(value: Any) -> dict[str, Any]:
    text = clamp_text(value)
    return {'rich_text': [{'text': {'content': text}}]} if text else {'rich_text': []}


def title_value(value: Any) -> dict[str, Any]:
    return {'title': [{'text': {'content': clamp_text(value)}}]}


def select_value(value: Any, allowed: set[str] | None = None, default: str | None = None) -> dict[str, Any]:
    name = q(value)
    if allowed is not None and name not in allowed:
        name = default or ''
    if not name and default:
        name = default
    return {'select': {'name': name}} if name else {'select': None}


def multi_select_value(values: Any) -> dict[str, Any]:
    names = split_multi(values)
    return {'multi_select': [{'name': name[:100]} for name in names[:20]]}


def date_value(value: Any) -> dict[str, Any]:
    text = q(value)
    return {'date': {'start': text}} if text else {'date': None}


def load_env() -> None:
    for env_path in ENV_CANDIDATES:
        path = Path(env_path)
        if not path.exists():
            continue
        for raw in path.read_text(encoding='utf-8', errors='ignore').splitlines():
            if '=' not in raw or raw.lstrip().startswith('#'):
                continue
            key, value = raw.split('=', 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def load_token() -> str:
    load_env()
    token = os.getenv('NOTION_TOKEN') or os.getenv('NOTION_API_KEY')
    if token:
        return token
    raise SystemExit('NOTION token not found')


def notion_request(
    path: str,
    token: str,
    method: str = 'GET',
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode('utf-8')
    req = urllib.request.Request(
        f'https://api.notion.com/v1{path}',
        data=data,
        method=method,
        headers={
            'Authorization': f'Bearer {token}',
            'Notion-Version': NOTION_VERSION,
            'Content-Type': 'application/json',
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode('utf-8'))


def read_items(path: str | None) -> list[dict[str, Any]]:
    text = Path(path).read_text(encoding='utf-8') if path else sys.stdin.read()
    data = json.loads(text)
    if not isinstance(data, list):
        raise SystemExit('Input must be a JSON array')
    return data


def title_from_property(prop: dict[str, Any] | None) -> str:
    parts = (prop or {}).get('title') or []
    return ''.join(part.get('plain_text', '') for part in parts).strip()


def rich_text_from_property(prop: dict[str, Any] | None) -> str:
    parts = (prop or {}).get('rich_text') or []
    return ''.join(part.get('plain_text', '') for part in parts).strip()


def url_from_property(prop: dict[str, Any] | None) -> str:
    return q((prop or {}).get('url'))


def fetch_existing_index(data_source_id: str, token: str) -> tuple[dict[str, str], dict[str, str], int]:
    url_to_page: dict[str, str] = {}
    canonical_to_page: dict[str, str] = {}
    total = 0
    cursor = None
    while True:
        payload: dict[str, Any] = {'page_size': 100}
        if cursor:
            payload['start_cursor'] = cursor
        data = notion_request(f'/data_sources/{data_source_id}/query', token, method='POST', payload=payload)
        for row in data.get('results', []):
            total += 1
            page_id = q(row.get('id'))
            props = row.get('properties', {})
            title = title_from_property(props.get(TITLE_PROP))
            organization = rich_text_from_property(props.get(ORG_PROP))
            url = url_from_property(props.get(URL_PROP))
            if url:
                url_to_page[url] = page_id
            canonical = make_canonical_key(title, organization)
            if canonical:
                canonical_to_page[canonical] = page_id
        if not data.get('has_more'):
            break
        cursor = data.get('next_cursor')
    return url_to_page, canonical_to_page, total


def make_canonical_key(title: Any, organization: Any) -> str:
    title_norm = norm(title)
    org_norm = norm(organization)
    if not title_norm:
        return ''
    return f'{org_norm} | {title_norm}'


def normalize_business_required(value: Any) -> str:
    text = q(value)
    lowered = text.lower()
    if lowered in {'true', 'yes', 'required', '필요'}:
        return '필요'
    if lowered in {'false', 'no', 'optional', '불필요'}:
        return '불필요'
    if lowered in {'conditional', '조건부'}:
        return '조건부'
    return ''


def build_properties(item: dict[str, Any]) -> dict[str, Any]:
    summary = q(item.get('summary'))
    why_relevant = q(item.get('why_relevant'))
    summary_block = summary
    if why_relevant:
        summary_block = f'{summary}\n\n왜 relevant: {why_relevant}' if summary else f'왜 relevant: {why_relevant}'
    properties: dict[str, Any] = {
        TITLE_PROP: title_value(item.get('title')),
        ORG_PROP: rich_text_value(item.get('organization')),
        DEADLINE_PROP: date_value(item.get('deadline')),
        START_DATE_PROP: date_value(item.get('start_date')),
        URL_PROP: {'url': q(item.get('url')) or None},
        SUMMARY_PROP: rich_text_value(summary_block),
        FIT_PROP: select_value(item.get('fit'), VALID_FIT),
        STATUS_PROP: select_value(item.get('status'), VALID_STATUS, default='신규'),
        FIELDS_PROP: multi_select_value(item.get('fields')),
        PROGRAM_TYPES_PROP: multi_select_value(item.get('program_types')),
        TARGETS_PROP: multi_select_value(item.get('targets')),
        BENEFIT_PROP: rich_text_value(item.get('benefit')),
        REGION_PROP: select_value(item.get('region'), VALID_REGION),
        BUSINESS_REQUIRED_PROP: select_value(
            normalize_business_required(item.get('business_required')),
            VALID_BIZ_REQUIRED,
        ),
    }
    return properties


def validate_item(item: dict[str, Any]) -> list[str]:
    required = ['title', 'organization', 'deadline', 'url', 'summary', 'why_relevant']
    return [field for field in required if not q(item.get(field))]


def create_page(data_source_id: str, token: str, properties: dict[str, Any]) -> dict[str, Any]:
    payload = {'parent': {'type': 'data_source_id', 'data_source_id': data_source_id}, 'properties': properties}
    return notion_request('/pages', token, method='POST', payload=payload)


def update_page(page_id: str, token: str, properties: dict[str, Any]) -> dict[str, Any]:
    payload = {'properties': properties}
    return notion_request(f'/pages/{page_id}', token, method='PATCH', payload=payload)


def summarize_http_error(exc: urllib.error.HTTPError) -> dict[str, Any]:
    body = exc.read().decode('utf-8', errors='ignore')
    return {
        'status': exc.code,
        'reason': q(exc.reason),
        'body': body[:800],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description='Upsert biz support radar rows into Notion')
    parser.add_argument('--input', help='Path to JSON array input. Defaults to stdin')
    parser.add_argument('--data-source-id', default=DEFAULT_DATA_SOURCE_ID)
    args = parser.parse_args()

    token = load_token()
    data_source_id = q(args.data_source_id) or DEFAULT_DATA_SOURCE_ID
    items = read_items(args.input)
    url_to_page, canonical_to_page, before_count = fetch_existing_index(data_source_id, token)

    inserted = 0
    updated = 0
    skipped_invalid = 0
    failed_requests = 0
    invalid_details: list[dict[str, Any]] = []
    request_failures: list[dict[str, Any]] = []

    for item in items:
        title = q(item.get('title'))
        organization = q(item.get('organization'))
        url = q(item.get('url'))
        missing = validate_item(item)
        if missing:
            skipped_invalid += 1
            invalid_details.append({
                'title': title or '(untitled)',
                'organization': organization,
                'missing': missing,
            })
            continue

        canonical = make_canonical_key(title, organization)
        page_id = url_to_page.get(url) or canonical_to_page.get(canonical)
        properties = build_properties(item)
        try:
            if page_id:
                update_page(page_id, token, properties)
                updated += 1
            else:
                created = create_page(data_source_id, token, properties)
                page_id = q(created.get('id'))
                inserted += 1
        except urllib.error.HTTPError as exc:
            failed_requests += 1
            request_failures.append({
                'title': title,
                'organization': organization,
                'url': url,
                **summarize_http_error(exc),
            })
            continue

        if page_id:
            if url:
                url_to_page[url] = page_id
            if canonical:
                canonical_to_page[canonical] = page_id

    result = {
        'data_source_id': data_source_id,
        'input_count': len(items),
        'inserted': inserted,
        'updated': updated,
        'skipped_invalid': skipped_invalid,
        'failed_requests': failed_requests,
        'before_count': before_count,
        'after_count': before_count + inserted,
        'invalid_details': invalid_details,
        'request_failures': request_failures,
    }
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
