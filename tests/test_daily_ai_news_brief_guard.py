import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GUARD_PATH = ROOT / "scripts" / "daily_ai_news_brief_guard.py"
spec = importlib.util.spec_from_file_location("daily_ai_news_brief_guard", GUARD_PATH)
guard = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(guard)


def base_item(**overrides):
    item = {
        "title": "OpenAI Responses API migration notice",
        "date": "2026-07-22",
        "source": "OpenAI",
        "type": "api",
        "topics": ["agents"],
        "insight": "Migration affects agent runtime planning.",
        "url": "https://developers.openai.com/api/docs/changelog",
        "priority": "high",
        "status": "new",
        "week": "30",
        "source_url_verified": True,
        "source_url_checked_at": "2026-07-22 05:30 KST",
        "source_claims": ["Responses API migration"],
    }
    item.update(overrides)
    return item


def test_guard_requires_explicit_source_verification(monkeypatch):
    monkeypatch.setattr(
        guard.append,
        "fetch_url_status",
        lambda url: (200, url, "OpenAI Responses API migration notice"),
    )

    reasons = guard.append.validate_item(base_item(source_url_verified=False))

    assert "source_url_verified_required" in reasons


def test_guard_rejects_claims_not_found_in_official_source(monkeypatch):
    monkeypatch.setattr(
        guard.append,
        "fetch_url_status",
        lambda url: (200, url, "OpenAI Responses API migration notice"),
    )

    reasons = guard.append.validate_item(base_item(source_claims=["GPT-5.5 migration notice"]))

    assert any(reason.startswith("claim_not_found_in_source:") for reason in reasons)


def test_guard_rejects_untrusted_domain_for_known_source(monkeypatch):
    monkeypatch.setattr(
        guard.append,
        "fetch_url_status",
        lambda url: (200, url, "OpenAI Responses API migration notice"),
    )

    reasons = guard.append.validate_item(
        base_item(url="https://example.com/openai-changelog")
    )

    assert any(reason.startswith("untrusted_source_domain:") for reason in reasons)


def test_guard_accepts_verified_claim_on_trusted_domain(monkeypatch):
    body = "OpenAI Responses API migration notice for agent runtime planning."
    monkeypatch.setattr(guard.append, "fetch_url_status", lambda url: (200, url, body))

    reasons = guard.append.validate_item(base_item())

    assert reasons == []
