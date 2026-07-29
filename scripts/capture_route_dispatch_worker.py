#!/usr/bin/env python3
"""Dispatch approved capture routes through the authenticated local Ops API."""

from __future__ import annotations

import argparse
import json
import os
from typing import Any, Callable
from urllib.parse import quote, urlencode

try:
    from capture_route_dispatch import request_json
except ImportError:  # pragma: no cover - module path fallback for tests/imports
    from scripts.capture_route_dispatch import request_json


HttpRequest = Callable[..., tuple[int, dict[str, Any] | str]]


def _organization_ids(raw: str) -> list[str]:
    return list(dict.fromkeys(value.strip() for value in raw.split(",") if value.strip()))


def run_once(
    base_url: str,
    organization_ids: list[str],
    token: str | None,
    *,
    max_attempts: int = 3,
    http_request: HttpRequest = request_json,
) -> dict[str, Any]:
    resolved_organizations = list(organization_ids)
    summary: dict[str, Any] = {
        "ok": True,
        "organizations": 0,
        "eligible": 0,
        "dispatched": 0,
        "failed": 0,
        "skippedMaxAttempts": 0,
        "results": [],
    }
    if not resolved_organizations:
        status, body = http_request(f"{base_url}/capture-routes/organizations", token=token)
        if status != 200 or not isinstance(body, dict):
            summary["ok"] = False
            summary["failed"] = 1
            summary["results"].append({"ok": False, "stage": "discover", "statusCode": status})
            return summary
        raw_organizations = body.get("items") or body.get("data") or []
        resolved_organizations = _organization_ids(
            ",".join(str(value) for value in raw_organizations) if isinstance(raw_organizations, list) else ""
        )
    summary["organizations"] = len(resolved_organizations)
    for organization_id in resolved_organizations:
        query = urlencode({"organizationId": organization_id})
        status, body = http_request(f"{base_url}/capture-routes?{query}", token=token)
        if status != 200 or not isinstance(body, dict):
            summary["ok"] = False
            summary["failed"] += 1
            summary["results"].append({"organizationId": organization_id, "ok": False, "stage": "list", "statusCode": status})
            continue
        items = body.get("items") or body.get("data") or []
        for item in items:
            if not isinstance(item, dict) or item.get("status") not in {"approved", "dispatch_failed"}:
                continue
            capture_id = str(item.get("captureId") or "").strip()
            if not capture_id:
                continue
            previous = item.get("dispatch") if isinstance(item.get("dispatch"), dict) else {}
            try:
                attempts = max(0, int(previous.get("attempt") or 0))
            except (TypeError, ValueError):
                attempts = 0
            if attempts >= max_attempts:
                summary["skippedMaxAttempts"] += 1
                continue
            summary["eligible"] += 1
            dispatch_url = f"{base_url}/capture-routes/{quote(capture_id, safe='')}/dispatch"
            dispatch_status, dispatch_body = http_request(
                dispatch_url,
                method="POST",
                token=token,
                payload={"organizationId": organization_id},
            )
            ok = 200 <= dispatch_status < 300 and isinstance(dispatch_body, dict) and bool(dispatch_body.get("ok"))
            summary["dispatched" if ok else "failed"] += 1
            summary["ok"] = summary["ok"] and ok
            summary["results"].append(
                {
                    "organizationId": organization_id,
                    "captureId": capture_id,
                    "ok": ok,
                    "stage": "dispatch",
                    "statusCode": dispatch_status,
                }
            )
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=os.getenv("MISSION_CONTROL_BASE_URL", "http://127.0.0.1:8792"))
    parser.add_argument(
        "--organization-ids",
        default=os.getenv("CAPTURE_ROUTE_ORGANIZATION_IDS", ""),
    )
    parser.add_argument("--max-attempts", type=int, default=int(os.getenv("CAPTURE_ROUTE_MAX_DISPATCH_ATTEMPTS", "3")))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    organizations = _organization_ids(args.organization_ids)
    token = (
        os.getenv("MISSION_CONTROL_SHARED_TOKEN", "").strip()
        or os.getenv("OPS_CTL_EXEC_ADMIN_TOKEN", "").strip()
        or os.getenv("OPS_CTL_EXEC_TOKEN", "").strip()
        or os.getenv("OPS_CTL_TOKEN", "").strip()
        or None
    )
    result = run_once(
        args.base_url.rstrip("/"),
        organizations,
        token,
        max_attempts=max(1, args.max_attempts),
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
