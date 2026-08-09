#!/usr/bin/env python3
"""Read consent-gated Health Memory through the Kernel API v0.

This is an operator/readback CLI for Hermes and Live Run. It never opens a
database connection and never prints the API token. Full PHI output requires
the explicit ``--json`` flag; the default output is a PHI-free count summary.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class HealthMemoryConfig:
    base_url: str
    api_token: str
    service_account_id: str
    organization_id: str
    subject_person_id: str
    runtime: str


def _required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ValueError(f"{name} is required")
    return value


def load_config() -> HealthMemoryConfig:
    return HealthMemoryConfig(
        base_url=_required_env("HEALTH_MEMORY_BASE_URL"),
        api_token=_required_env("HEALTH_MEMORY_API_TOKEN"),
        service_account_id=_required_env("HEALTH_MEMORY_SERVICE_ACCOUNT_ID"),
        organization_id=_required_env("HEALTH_MEMORY_ORGANIZATION_ID"),
        subject_person_id=_required_env("HEALTH_MEMORY_SUBJECT_PERSON_ID"),
        runtime=os.environ.get("HEALTH_MEMORY_RUNTIME", "hermes").strip() or "hermes",
    )


def build_request(config: HealthMemoryConfig, limit: int, request_id: str) -> dict[str, Any]:
    return {
        "domain": "memory",
        "subjectPersonId": config.subject_person_id,
        "limit": max(1, min(limit, 20)),
        "context": {
            "serviceAccountId": config.service_account_id,
            "organizationId": config.organization_id,
            "scopes": ["memory:read"],
        },
        "provenance": {
            "runtime": config.runtime,
            "runtimeVersion": "hermes-health-memory-cli-v1",
            "requestId": request_id,
        },
    }


def redact_request(request: dict[str, Any]) -> dict[str, Any]:
    redacted = json.loads(json.dumps(request))
    redacted["subjectPersonId"] = "<subject>"
    redacted["context"]["organizationId"] = "<organization>"
    return redacted


def fetch_context(config: HealthMemoryConfig, request: dict[str, Any]) -> dict[str, Any]:
    body = json.dumps(request).encode("utf-8")
    http_request = urllib.request.Request(
        f"{config.base_url.rstrip('/')}/api/kernel/v0",
        data=body,
        method="POST",
        headers={
            "content-type": "application/json",
            "x-hermes-api-key": config.api_token,
        },
    )
    try:
        with urllib.request.urlopen(http_request, timeout=30) as response:
            response_body = json.loads(response.read().decode("utf-8"))
            status = response.status
    except urllib.error.HTTPError as error:
        raise RuntimeError(f"Health Memory API rejected request: HTTP {error.code}") from None
    except (urllib.error.URLError, TimeoutError) as error:
        raise RuntimeError(f"Health Memory API transport failed: {error.__class__.__name__}") from None
    except json.JSONDecodeError:
        raise RuntimeError("Health Memory API returned invalid JSON") from None

    if status < 200 or status >= 300 or response_body.get("success") is not True:
        code = response_body.get("code") if isinstance(response_body, dict) else None
        suffix = f" ({code})" if isinstance(code, str) else ""
        raise RuntimeError(f"Health Memory API rejected request: HTTP {status}{suffix}")

    context = response_body.get("data", {}).get("context")
    if not isinstance(context, dict) or context.get("schemaVersion") != "health-memory-context.v1":
        raise RuntimeError("Health Memory API returned an invalid context contract")
    return context


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--request-id", default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json", action="store_true", dest="json_output")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    try:
        config = load_config()
        request = build_request(config, args.limit, args.request_id or str(uuid.uuid4()))
        if args.dry_run:
            print(json.dumps(redact_request(request), ensure_ascii=False, indent=2))
            print("[dry-run] not sent.")
            return 0
        context = fetch_context(config, request)
        if args.json_output:
            print(json.dumps(context, ensure_ascii=False))
        else:
            print(
                "health-memory read ok: "
                f"schema={context['schemaVersion']} items={len(context.get('items', []))}"
            )
        return 0
    except (ValueError, RuntimeError) as error:
        print(f"health-memory read failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
