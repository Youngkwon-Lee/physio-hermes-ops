"""Phase 5 (Hermes Runtime Split) contract tests for the EvalOps P0 pass-through.

These are self-contained: they drive the read-model helper and the /evalops/p0
endpoint in-process against a temp artifact dir, so they need neither the live
:8791 runtime nor any physio_app state.
"""

import http.client
import json
import threading
from http.server import ThreadingHTTPServer

import mission_control_api as api

READ_MODEL = {
    "schemaVersion": "evalops-p0-gate/v1",
    "generatedAt": "2026-07-09T00:00:00.000Z",
    "status": "watch",
    "summary": "2/2 P0 EvalOps workflows passing · 0 fail · 0 blocked",
    "reportPath": "docs/reports/evalops-p0-gate-summary.md",
    "workflows": [],
    "totals": {"workflowCount": 2, "passingWorkflowCount": 2, "fixtureCount": 10},
    "releaseCriteria": [],
    "smokeEvidence": [],
    "nextRequiredWork": [],
}


def _write_artifact(app_path, payload):
    output_dir = app_path / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "evalops-p0-mission-control.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )


def test_evalops_p0_passes_the_physio_app_artifact_through_verbatim(tmp_path, monkeypatch):
    _write_artifact(tmp_path, READ_MODEL)
    monkeypatch.setenv("AGENT_OS_TARGET_APP_PATH", str(tmp_path))

    result = api.get_evalops_p0_read_model()

    # Verbatim pass-through — Hermes must not re-transform (no dual existence).
    assert result == READ_MODEL


def test_evalops_p0_returns_a_well_formed_missing_model_when_absent(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_OS_TARGET_APP_PATH", str(tmp_path))

    result = api.get_evalops_p0_read_model()

    assert result["status"] == "missing"
    assert result["summary"] == "EvalOps P0 JSON report has not been generated yet."
    assert result["workflows"] == []
    assert result["totals"]["workflowCount"] == 0
    # Every declared field is present so the physio_app client never sees a partial.
    for key in (
        "generatedAt",
        "schemaVersion",
        "status",
        "summary",
        "reportPath",
        "workflows",
        "totals",
        "releaseCriteria",
        "smokeEvidence",
        "nextRequiredWork",
    ):
        assert key in result


def test_evalops_p0_endpoint_serves_the_read_model_over_http(tmp_path, monkeypatch):
    _write_artifact(tmp_path, {**READ_MODEL, "status": "pass"})
    monkeypatch.setenv("AGENT_OS_TARGET_APP_PATH", str(tmp_path))
    monkeypatch.setattr(api, "API_KEY", "")  # auth off for the in-process test

    server = ThreadingHTTPServer(("127.0.0.1", 0), api.MissionControlHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        conn = http.client.HTTPConnection("127.0.0.1", server.server_address[1])
        conn.request("GET", "/evalops/p0")
        response = conn.getresponse()
        body = json.loads(response.read())
        conn.close()
    finally:
        server.shutdown()
        server.server_close()

    assert response.status == 200
    assert body["success"] is True
    assert body["data"]["status"] == "pass"
    assert body["data"]["schemaVersion"] == "evalops-p0-gate/v1"


SNAPSHOT_READ_MODELS = {
    "agentOps": {"schemaVersion": "agentops-readiness/v1", "status": "watch"},
    "devOps": {"schemaVersion": "devops-readiness/v1", "status": "watch"},
    "evalOpsP0": {"schemaVersion": "evalops-p0-gate/v1", "status": "pass"},
    "mlOps": {"schemaVersion": "mlops-readiness/v1", "status": "early"},
}


def _write_snapshot_read_models(app_path, payload):
    output_dir = app_path / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "mission-control-snapshot-read-models.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )


def test_snapshot_read_models_pass_through_the_artifact(tmp_path, monkeypatch):
    _write_snapshot_read_models(tmp_path, SNAPSHOT_READ_MODELS)
    monkeypatch.setenv("AGENT_OS_TARGET_APP_PATH", str(tmp_path))

    result = api.get_mission_control_snapshot_read_models()

    assert result == SNAPSHOT_READ_MODELS


def test_snapshot_read_models_return_empty_when_absent(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_OS_TARGET_APP_PATH", str(tmp_path))
    assert api.get_mission_control_snapshot_read_models() == {}


def test_snapshot_read_models_return_empty_when_malformed(tmp_path, monkeypatch):
    _write_snapshot_read_models(tmp_path, ["not", "a", "dict"])
    monkeypatch.setenv("AGENT_OS_TARGET_APP_PATH", str(tmp_path))
    # Malformed artifact must not break the snapshot spread.
    assert api.get_mission_control_snapshot_read_models() == {}


def test_snapshot_endpoint_spreads_the_ops_read_models(tmp_path, monkeypatch):
    _write_snapshot_read_models(tmp_path, SNAPSHOT_READ_MODELS)
    monkeypatch.setenv("AGENT_OS_TARGET_APP_PATH", str(tmp_path))
    monkeypatch.setattr(api, "API_KEY", "")

    server = ThreadingHTTPServer(("127.0.0.1", 0), api.MissionControlHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        conn = http.client.HTTPConnection("127.0.0.1", server.server_address[1])
        conn.request("GET", "/snapshot?organizationId=11111111-1111-4111-8111-111111111111")
        response = conn.getresponse()
        body = json.loads(response.read())
        conn.close()
    finally:
        server.shutdown()
        server.server_close()

    assert response.status == 200
    assert body["success"] is True
    # Existing fields still present, plus the spread ops read models.
    assert "runs" in body["data"]
    assert body["data"]["agentOps"]["schemaVersion"] == "agentops-readiness/v1"
    assert body["data"]["evalOpsP0"]["status"] == "pass"
