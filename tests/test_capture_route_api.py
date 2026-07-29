from __future__ import annotations

import http.client
import json
import threading
from http.server import ThreadingHTTPServer

import ops_control_api as api
from capture_route_dispatch import CaptureRouteStore


def request(server, method, path, payload=None):
    connection = http.client.HTTPConnection("127.0.0.1", server.server_address[1])
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Content-Type": "application/json"} if body else {}
    connection.request(method, path, body=body, headers=headers)
    response = connection.getresponse()
    parsed = json.loads(response.read())
    connection.close()
    return response.status, parsed


def candidate_queue(sensitivity="normal"):
    return {
        "schema": "capture-route-decision-v1",
        "approval_required": True,
        "items": [
            {
                "capture_id": "CAP-API",
                "source_path": "operations/raw/mobile-note-deltas/example.md",
                "source_schema": "openminis-mobile-candidate-v1",
                "title": "제품 파일럿 피드백",
                "summary": "치료사 피드백을 제품 운영에서 검토한다.",
                "sensitivity": sensitivity,
                "proposed_destination": "physio_app",
                "proposed_object_type": "provider_feedback",
            }
        ],
    }


def test_capture_route_sync_snapshot_and_approval(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "CAPTURE_ROUTE_STORE", CaptureRouteStore(tmp_path / "routes.json"))
    monkeypatch.setattr(api, "REQUIRE_TOKEN", False)
    monkeypatch.setattr(api, "AUDIT_LOG", tmp_path / "audit.jsonl")
    monkeypatch.setattr(api, "HANDOFF_INBOX_PATH", tmp_path / "handoff.json")
    monkeypatch.setattr(api, "LEGACY_HANDOFF_INBOX_PATH", tmp_path / "legacy.json")

    server = ThreadingHTTPServer(("127.0.0.1", 0), api.Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        status, body = request(
            server,
            "POST",
            "/capture-routes/sync",
            {"organizationId": "org-1", "queue": candidate_queue()},
        )
        assert status == 200
        assert body["data"]["created"] == 1

        status, body = request(server, "GET", "/capture-routes/organizations")
        assert status == 200
        assert body["items"] == ["org-1"]

        status, body = request(server, "GET", "/capture-routes?organizationId=org-1")
        assert status == 200
        assert body["items"][0]["status"] == "pending"

        status, body = request(
            server,
            "POST",
            "/capture-routes/CAP-API/decision",
            {"organizationId": "org-1", "decision": "approve", "actor": "youngkwon"},
        )
        assert status == 200
        assert body["item"]["status"] == "approved"

        monkeypatch.setenv("MISSION_CONTROL_BASE_URL", f"http://127.0.0.1:{server.server_address[1]}")
        status, body = request(
            server,
            "POST",
            "/capture-routes/CAP-API/dispatch",
            {"organizationId": "org-1"},
        )
        assert status == 200
        assert body["item"]["ok"] is True
        assert body["item"]["readback"]["recordId"] == "capture-physio_app-cap-api"

        status, body = request(server, "GET", "/snapshot?organizationId=org-1")
        assert status == 200
        assert body["data"]["captureRoutes"][0]["captureId"] == "CAP-API"
        assert body["data"]["captureRoutes"][0]["status"] == "dispatched"
    finally:
        server.shutdown()
        server.server_close()


def test_restricted_route_rejects_approval(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "CAPTURE_ROUTE_STORE", CaptureRouteStore(tmp_path / "routes.json"))
    monkeypatch.setattr(api, "REQUIRE_TOKEN", False)
    monkeypatch.setattr(api, "AUDIT_LOG", tmp_path / "audit.jsonl")
    server = ThreadingHTTPServer(("127.0.0.1", 0), api.Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        request(
            server,
            "POST",
            "/capture-routes/sync",
            {"organizationId": "org-1", "queue": candidate_queue("restricted")},
        )
        status, body = request(
            server,
            "POST",
            "/capture-routes/CAP-API/decision",
            {"organizationId": "org-1", "decision": "approve", "actor": "youngkwon"},
        )
        assert status == 409
        assert "restricted" in body["error"]
    finally:
        server.shutdown()
        server.server_close()
