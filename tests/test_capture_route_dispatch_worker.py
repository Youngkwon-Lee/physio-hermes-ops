from __future__ import annotations

from capture_route_dispatch_worker import _organization_ids, run_once


def test_organization_ids_are_trimmed_and_deduplicated():
    assert _organization_ids(" org-1,org-2,org-1, ") == ["org-1", "org-2"]


def test_worker_dispatches_only_eligible_routes_and_caps_retries():
    calls = []

    def fake_request(url, **kwargs):
        calls.append((url, kwargs))
        if "/capture-routes?" in url:
            return 200, {
                "items": [
                    {"captureId": "CAP-APPROVED", "status": "approved", "dispatch": None},
                    {"captureId": "CAP-FAILED", "status": "dispatch_failed", "dispatch": {"attempt": 3}},
                    {"captureId": "CAP-PENDING", "status": "pending", "dispatch": None},
                ]
            }
        return 200, {"ok": True}

    result = run_once("http://mission.test", ["org-1"], "test-token", http_request=fake_request)
    assert result["ok"] is True
    assert result["eligible"] == 1
    assert result["dispatched"] == 1
    assert result["skippedMaxAttempts"] == 1
    assert len(calls) == 2
    assert calls[1][0].endswith("/capture-routes/CAP-APPROVED/dispatch")
    assert calls[1][1]["payload"] == {"organizationId": "org-1"}


def test_worker_reports_list_failure_without_leaking_response_body():
    def fake_request(url, **kwargs):
        return 503, "upstream secret-shaped error"

    result = run_once("http://mission.test", ["org-1"], "test-token", http_request=fake_request)
    assert result["ok"] is False
    assert result["failed"] == 1
    assert "secret-shaped" not in str(result)
