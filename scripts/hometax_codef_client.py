#!/usr/bin/env python3
from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from typing import Any

import requests

CODEF_OAUTH_URL_PROD = "https://oauth.codef.io/oauth/token"
CODEF_OAUTH_URL_SANDBOX = "https://sandbox.codef.io/oauth/token"
CODEF_API_BASE_PROD = "https://api.codef.io"
CODEF_API_BASE_SANDBOX = "https://sandbox.codef.io"
DEFAULT_ENV_FILE = Path.home() / ".config" / "physio-hermes-ops" / "hometax-codef.env"

DOC_PATHS = {
    "income_proof": "/v1/kr/public/nt/proof-issue/income-amount",
    "tax_clearance": "/v1/kr/public/nt/proof-issue/tax-clearance",
    "biz_reg_proof": "/v1/kr/public/nt/proof-issue/business-registration",
    "vat_base_proof": "/v1/kr/public/nt/proof-issue/vat-base",
}

DOC_META = {
    "income_proof": {"label": "소득금액증명", "requires_year": True},
    "tax_clearance": {"label": "납세증명", "requires_year": False},
    "biz_reg_proof": {"label": "사업자등록증명", "requires_year": False},
    "vat_base_proof": {"label": "부가가치세 과세표준증명", "requires_year": False},
}


class HometaxCodefError(RuntimeError):
    """CODEF/Hometax integration error."""


def env_file_path() -> Path:
    custom = os.getenv("HOMETAX_CODEF_ENV_FILE", "").strip()
    return Path(custom).expanduser() if custom else DEFAULT_ENV_FILE


def _read_env_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    result: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        result[key.strip()] = value.strip().strip('"').strip("'")
    return result


def _resolve_value(key: str, file_values: dict[str, str]) -> tuple[str | None, str | None]:
    env_value = os.getenv(key)
    if env_value:
        return env_value, "env"
    if key in file_values and file_values[key]:
        return file_values[key], "envfile"
    return None, None


def load_credentials() -> dict[str, Any]:
    values = _read_env_file(env_file_path())
    client_id, client_id_src = _resolve_value("CODEF_CLIENT_ID", values)
    client_secret, client_secret_src = _resolve_value("CODEF_CLIENT_SECRET", values)
    public_key, public_key_src = _resolve_value("CODEF_PUBLIC_KEY", values)
    sandbox_raw, sandbox_src = _resolve_value("CODEF_SANDBOX", values)
    sandbox = False if sandbox_raw == "0" else True
    sandbox_source = sandbox_src or "default"
    return {
        "client_id": client_id,
        "client_secret": client_secret,
        "public_key": public_key,
        "sandbox": sandbox,
        "sources": {
            "client_id": client_id_src,
            "client_secret": client_secret_src,
            "public_key": public_key_src,
            "sandbox": sandbox_source,
        },
        "env_file": str(env_file_path()),
    }


def credentials_status() -> dict[str, Any]:
    creds = load_credentials()
    return {
        "ok": True,
        "provider": "codef",
        "configured": bool(creds["client_id"] and creds["client_secret"]),
        "sandbox": creds["sandbox"],
        "available_doc_types": list(DOC_PATHS.keys()),
        "credential_sources": creds["sources"],
        "env_file": creds["env_file"],
    }


def docs_catalog() -> list[dict[str, Any]]:
    return [
        {"doc_type": key, **DOC_META[key]}
        for key in DOC_PATHS.keys()
    ]


def mask_identity(value: str | None) -> str:
    value = (value or "").strip()
    if not value:
        return ""
    if len(value) <= 4:
        return "*" * len(value)
    middle = max(2, len(value) - 8)
    return f"{value[:4]}{'*' * middle}{value[-4:]}"


def _oauth_token(creds: dict[str, Any]) -> str:
    client_id = creds.get("client_id")
    client_secret = creds.get("client_secret")
    if not client_id or not client_secret:
        raise HometaxCodefError("CODEF credentials not configured")
    oauth_url = CODEF_OAUTH_URL_SANDBOX if creds["sandbox"] else CODEF_OAUTH_URL_PROD
    auth = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    response = requests.post(
        oauth_url,
        data={"grant_type": "client_credentials", "scope": "read"},
        headers={
            "Authorization": f"Basic {auth}",
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        },
        timeout=15,
    )
    response.raise_for_status()
    payload = response.json()
    token = payload.get("access_token")
    if not token:
        raise HometaxCodefError(f"CODEF OAuth response missing access_token: {payload}")
    return token


def call_codef(path: str, body: dict[str, Any]) -> dict[str, Any]:
    creds = load_credentials()
    token = _oauth_token(creds)
    api_base = CODEF_API_BASE_SANDBOX if creds["sandbox"] else CODEF_API_BASE_PROD
    response = requests.post(
        api_base + path,
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=UTF-8",
            "Accept": "application/json",
        },
        timeout=30,
    )
    response.raise_for_status()
    try:
        return response.json()
    except requests.JSONDecodeError as exc:
        raise HometaxCodefError(f"CODEF response was not valid JSON: {response.text[:200]}") from exc


def summarize_result(payload: dict[str, Any]) -> dict[str, Any]:
    result = payload.get("result") or {}
    data = payload.get("data") or {}
    summary: dict[str, Any] = {
        "code": result.get("code"),
        "message": result.get("message"),
    }
    for key, value in data.items():
        if isinstance(value, (int, float, bool)):
            summary[key] = value
        elif isinstance(value, str) and len(value) <= 120:
            summary[key] = value
    return summary


def fetch_hometax(
    *,
    doc_type: str,
    identity: str,
    user_name: str,
    login_type: str = "6",
    year: str | None = None,
    twoway_info: dict[str, Any] | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    if doc_type not in DOC_PATHS:
        raise ValueError(f"unsupported doc_type: {doc_type}")
    status = credentials_status()
    if dry_run:
        return {
            "ok": True,
            "provider": "codef",
            "stage": "dry_run",
            "doc_type": doc_type,
            "masked_identity": mask_identity(identity),
            "sandbox": status["sandbox"],
        }
    creds = load_credentials()
    if not creds["client_id"] or not creds["client_secret"]:
        raise HometaxCodefError("CODEF credentials not configured")

    body: dict[str, Any] = {
        "organization": "0001",
        "loginType": login_type,
        "loginTypeLevel": "1",
        "userName": user_name,
        "identity": identity,
        "simpleAuth": "1",
    }
    if year:
        body["year"] = year
    if twoway_info:
        body["is2Way"] = True
        body["twoWayInfo"] = twoway_info

    raw = call_codef(DOC_PATHS[doc_type], body)
    result = raw.get("result") or {}
    data = raw.get("data") or {}
    if result.get("code") == "CF-03002" or data.get("continue2Way"):
        return {
            "ok": True,
            "provider": "codef",
            "stage": "waiting_user_auth",
            "doc_type": doc_type,
            "message": "카카오톡/PASS 승인 후 twoway_info로 재호출하세요.",
            "masked_identity": mask_identity(identity),
            "twoway_info": data.get("twoWayInfo") or raw.get("twoWayInfo"),
        }
    return {
        "ok": True,
        "provider": "codef",
        "stage": "completed",
        "doc_type": doc_type,
        "masked_identity": mask_identity(identity),
        "data_summary": summarize_result(raw),
        "raw": raw,
    }
