#!/usr/bin/env python3
import argparse
import importlib.util
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

ROUTER_SCRIPT = Path('/home/yk/physio-hermes-ops/scripts/daily_rehab_brief_notion_router.py')
spec = importlib.util.spec_from_file_location('daily_rehab_brief_notion_router', ROUTER_SCRIPT)
router = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(router)


def q(value: Any) -> str:
    if value is None:
        return ''
    return str(value).strip()


def norm(value: str) -> str:
    return ' '.join(q(value).lower().split())


def read_items(path: str) -> list[dict[str, Any]]:
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    if not isinstance(data, list):
        raise SystemExit('Input must be a JSON array')
    return data


def fetch_url(url: str, method: str = 'GET') -> tuple[int | None, str, str]:
    if not url.startswith(('http://', 'https://')):
        return None, url, 'url_not_http'
    headers = {'User-Agent': 'Mozilla/5.0 (Kinelo Ops rehab verifier)'}
    try:
        req = urllib.request.Request(url, method=method, headers=headers)
        with urllib.request.urlopen(req, timeout=20) as resp:
            body = '' if method == 'HEAD' else resp.read(512_000).decode('utf-8', errors='ignore')
            return int(resp.status), resp.geturl(), body
    except urllib.error.HTTPError as error:
        return int(error.code), url, error.read().decode('utf-8', errors='ignore')
    except Exception as error:
        return None, url, f'{type(error).__name__}: {error}'


def fetch_reachable(url: str) -> tuple[int | None, str, str]:
    status, final_url, body = fetch_url(url, 'HEAD')
    if status is not None and status < 400:
        return status, final_url, body
    return fetch_url(url, 'GET')


def fetch_body(url: str) -> str:
    status, _final_url, body = fetch_url(url, 'GET')
    if status is None or status >= 400:
        raise ValueError(f'url_unreachable:{status}:{url}')
    return body


def extract_arxiv_title(html: str) -> str:
    match = re.search(r'<h1[^>]*class="title[^>]*>\s*<span[^>]*>Title:\s*</span>\s*(.*?)\s*</h1>', html, re.I | re.S)
    if not match:
        return ''
    return ' '.join(re.sub(r'<[^>]+>', ' ', match.group(1)).split())


def extract_pubmed_title(html: str) -> str:
    match = re.search(r'<h1[^>]*class="heading-title"[^>]*>(.*?)</h1>', html, re.I | re.S)
    if not match:
        match = re.search(r'<title>(.*?)</title>', html, re.I | re.S)
    if not match:
        return ''
    title = re.sub(r'<[^>]+>', ' ', match.group(1))
    title = title.replace('- PubMed', '')
    return ' '.join(title.split())


def title_matches(expected: str, actual: str) -> bool:
    expected_norm = norm(expected)
    actual_norm = norm(actual)
    if not expected_norm or not actual_norm:
        return True
    return expected_norm in actual_norm or actual_norm in expected_norm


def validate_url_and_title(item: dict[str, Any]) -> list[str]:
    url = q(item.get('url'))
    title = q(item.get('title'))
    if not url:
        return []
    status, final_url, body = fetch_reachable(url)
    if status is None:
        return [f'url_unverified:{url}:{body[:120]}']
    if status >= 400:
        return [f'url_unreachable:{status}:{url}']
    parsed = urllib.parse.urlparse(final_url or url)
    host = parsed.netloc.lower()
    path = parsed.path
    if host.endswith('arxiv.org') and path.startswith('/abs/'):
        if not body:
            try:
                body = fetch_body(final_url or url)
            except Exception as error:
                return [f'url_unverified:{url}:{type(error).__name__}: {error}']
        actual = extract_arxiv_title(body)
        if actual and not title_matches(title, actual):
            return [f'url_title_mismatch: expected={title[:100]} actual={actual[:100]}']
    if 'pubmed.ncbi.nlm.nih.gov' in host:
        if not body:
            try:
                body = fetch_body(final_url or url)
            except Exception as error:
                return [f'url_unverified:{url}:{type(error).__name__}: {error}']
        actual = extract_pubmed_title(body)
        if actual and not title_matches(title, actual):
            return [f'url_title_mismatch: expected={title[:100]} actual={actual[:100]}']
    return []


def validate_item(item: dict[str, Any]) -> list[str]:
    if not isinstance(item, dict):
        return ['not_object']
    kind = router.classify_kind(item)
    missing = router.validate_item(item, kind)
    if missing:
        return missing
    return validate_url_and_title(item)


def main() -> int:
    parser = argparse.ArgumentParser(description='Validate and filter rehab AI brief candidates before Notion/second-brain writes')
    parser.add_argument('--input', required=True)
    parser.add_argument('--valid-output', required=True)
    parser.add_argument('--report-output', required=True)
    parser.add_argument('--min-valid', type=int, default=0)
    args = parser.parse_args()

    items = read_items(args.input)
    valid: list[dict[str, Any]] = []
    invalid: list[dict[str, Any]] = []
    duplicate_within_input: list[dict[str, Any]] = []
    seen_urls: set[str] = set()

    for index, item in enumerate(items):
        title = q(item.get('title')) if isinstance(item, dict) else '(non-object)'
        url = q(item.get('url')) if isinstance(item, dict) else ''
        reasons = validate_item(item)
        if url and url in seen_urls:
            duplicate_within_input.append({'index': index, 'title': title, 'url': url, 'reasons': ['duplicate_within_input']})
            continue
        if reasons:
            invalid.append({'index': index, 'title': title or '(untitled)', 'url': url, 'kind': router.classify_kind(item) if isinstance(item, dict) else 'unknown', 'reasons': reasons})
            continue
        if url:
            seen_urls.add(url)
        valid.append(item)

    report = {
        'input_count': len(items),
        'valid_count': len(valid),
        'invalid_count': len(invalid),
        'duplicate_within_input_count': len(duplicate_within_input),
        'valid_titles': [q(item.get('title')) for item in valid],
        'invalid_details': invalid,
        'duplicate_within_input_details': duplicate_within_input,
    }
    Path(args.valid_output).write_text(json.dumps(valid, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    Path(args.report_output).write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False))
    return 2 if len(valid) < args.min_valid else 0


if __name__ == '__main__':
    raise SystemExit(main())
