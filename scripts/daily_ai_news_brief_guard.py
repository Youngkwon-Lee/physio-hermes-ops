#!/usr/bin/env python3
import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

APPEND_SCRIPT = Path('/home/yk/physio-hermes-ops/scripts/daily_ai_news_brief_notion_append.py')
spec = importlib.util.spec_from_file_location('daily_ai_news_brief_notion_append', APPEND_SCRIPT)
append = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(append)


def q(value: Any) -> str:
    if value is None:
        return ''
    return str(value).strip()


def read_items(path: str) -> list[dict[str, Any]]:
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    if not isinstance(data, list):
        raise SystemExit('Input must be a JSON array')
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description='Validate and filter AI news brief candidates before Notion/second-brain writes')
    parser.add_argument('--input', required=True, help='Raw JSON array path')
    parser.add_argument('--valid-output', required=True, help='Path to write validated JSON array')
    parser.add_argument('--report-output', required=True, help='Path to write validation report JSON')
    parser.add_argument('--min-valid', type=int, default=0, help='Exit non-zero when valid_count is below this threshold')
    args = parser.parse_args()

    items = read_items(args.input)
    valid: list[dict[str, Any]] = []
    invalid: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    duplicate_within_input: list[dict[str, Any]] = []

    for index, item in enumerate(items):
        if not isinstance(item, dict):
            invalid.append({'index': index, 'title': '(non-object)', 'url': '', 'reasons': ['not_object']})
            continue
        title = q(item.get('title')) or '(untitled)'
        url = q(item.get('url'))
        reasons = append.validate_item(item)
        if url and url in seen_urls:
            duplicate_within_input.append({'index': index, 'title': title, 'url': url, 'reasons': ['duplicate_within_input']})
            continue
        if reasons:
            invalid.append({'index': index, 'title': title, 'url': url, 'reasons': reasons})
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

    if len(valid) < args.min_valid:
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
