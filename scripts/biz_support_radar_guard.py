#!/usr/bin/env python3
import argparse
import json
import re
import urllib.error
import urllib.request
from datetime import date, datetime
from pathlib import Path
from typing import Any

REQUIRED = ['title', 'organization', 'deadline', 'url', 'summary', 'why_relevant']
VALID_FIT = {'S', 'A', 'B', 'C'}
EVENT_WORDS = ['행사', '이벤트', '대회', '밋업', 'meetup', 'luma', 'event', 'conference', '세미나', '설명회', '데모데이']


def q(value: Any) -> str:
    if value is None:
        return ''
    return str(value).strip()


def parse_date(value: Any) -> date | None:
    text = q(value)
    if not text:
        return None
    for pattern in ['%Y-%m-%d', '%Y.%m.%d', '%Y/%m/%d']:
        try:
            return datetime.strptime(text[:10].replace('/', '-').replace('.', '-'), '%Y-%m-%d').date()
        except ValueError:
            pass
    match = re.search(r'(20\d{2})[.\-/년\s]+(\d{1,2})[.\-/월\s]+(\d{1,2})', text)
    if match:
        y, m, d = map(int, match.groups())
        try:
            return date(y, m, d)
        except ValueError:
            return None
    return None


def fetch_url_status(url: str) -> tuple[int | None, str]:
    if not url.startswith(('http://', 'https://')):
        return None, 'url_not_http'
    headers = {'User-Agent': 'Mozilla/5.0 (Kinelo Ops opportunity verifier)'}
    for method in ['HEAD', 'GET']:
        try:
            req = urllib.request.Request(url, method=method, headers=headers)
            with urllib.request.urlopen(req, timeout=20) as resp:
                return int(resp.status), resp.geturl()
        except urllib.error.HTTPError as error:
            if error.code in {403, 405} and method == 'HEAD':
                continue
            return int(error.code), error.reason or url
        except Exception as error:
            if method == 'GET':
                return None, f'{type(error).__name__}: {error}'
    return None, 'unknown_url_error'


def is_event(item: dict[str, Any]) -> bool:
    text = ' '.join(q(item.get(key)) for key in ['title', 'summary', 'program_types', 'fields', 'category', 'type', 'item_type']).lower()
    return any(word.lower() in text for word in EVENT_WORDS)


def validate_item(item: dict[str, Any], today: date) -> list[str]:
    errors = [field for field in REQUIRED if not q(item.get(field))]
    if errors:
        return errors
    if is_event(item):
        errors.append('event_not_for_notion')
    deadline = parse_date(item.get('deadline'))
    if deadline is None:
        errors.append(f'invalid_deadline:{q(item.get("deadline"))}')
    elif deadline < today:
        errors.append(f'expired_deadline:{deadline.isoformat()}')
    fit = q(item.get('fit'))
    if fit and fit not in VALID_FIT:
        errors.append(f'invalid_fit:{fit}')
    status, detail = fetch_url_status(q(item.get('url')))
    if status is None:
        errors.append(f'url_unverified:{detail[:120]}')
    elif status >= 400:
        errors.append(f'url_unreachable:{status}:{q(item.get("url"))}')
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description='Validate biz support radar candidates before Notion writes')
    parser.add_argument('--input', required=True)
    parser.add_argument('--valid-output', required=True)
    parser.add_argument('--report-output', required=True)
    parser.add_argument('--today', default=date.today().isoformat())
    parser.add_argument('--min-valid', type=int, default=0)
    args = parser.parse_args()

    today = parse_date(args.today)
    if today is None:
        raise SystemExit(f'invalid --today: {args.today}')
    data = json.loads(Path(args.input).read_text(encoding='utf-8'))
    if not isinstance(data, list):
        raise SystemExit('Input must be a JSON array')

    valid = []
    invalid = []
    seen_urls = set()
    duplicates = []
    for index, item in enumerate(data):
        if not isinstance(item, dict):
            invalid.append({'index': index, 'title': '(non-object)', 'url': '', 'reasons': ['not_object']})
            continue
        title = q(item.get('title')) or '(untitled)'
        url = q(item.get('url'))
        if url and url in seen_urls:
            duplicates.append({'index': index, 'title': title, 'url': url, 'reasons': ['duplicate_within_input']})
            continue
        reasons = validate_item(item, today)
        if reasons:
            invalid.append({'index': index, 'title': title, 'organization': q(item.get('organization')), 'url': url, 'reasons': reasons})
            continue
        if url:
            seen_urls.add(url)
        valid.append(item)

    report = {
        'input_count': len(data),
        'valid_count': len(valid),
        'invalid_count': len(invalid),
        'duplicate_within_input_count': len(duplicates),
        'valid_titles': [q(item.get('title')) for item in valid],
        'invalid_details': invalid,
        'duplicate_within_input_details': duplicates,
        'today': today.isoformat(),
    }
    Path(args.valid_output).write_text(json.dumps(valid, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    Path(args.report_output).write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False))
    return 2 if len(valid) < args.min_valid else 0


if __name__ == '__main__':
    raise SystemExit(main())
