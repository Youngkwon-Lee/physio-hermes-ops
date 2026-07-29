from __future__ import annotations

from pathlib import Path

import pytest

from capture_route_dispatch import CaptureRouteStore, DispatchBlocked, dispatch_route


def queue(*items):
    return {"schema": "capture-route-decision-v1", "approval_required": True, "items": list(items)}


def candidate(capture_id="CAP-ONE", destination="kinelo_ops", sensitivity="normal"):
    return {
        "capture_id": capture_id,
        "source_path": "operations/raw/mobile-note-deltas/example.md",
        "source_schema": "openminis-mobile-candidate-v1",
        "captured_at": "2026-07-29T09:00:00+09:00",
        "title": "신규 센터 후속 미팅",
        "summary": "센터 담당자와 후속 미팅을 잡는다.",
        "sensitivity": sensitivity,
        "suggested_route": "company",
        "proposed_destination": destination,
        "proposed_object_type": "action",
        "confidence": "medium",
        "reason": "company operations signal matched",
    }


def test_sync_is_idempotent_and_preserves_decisions(tmp_path: Path):
    store = CaptureRouteStore(tmp_path / "routes.json")
    assert store.sync("org-1", queue(candidate())) == {"created": 1, "updated": 0, "preserved": 0, "total": 1}
    assert store.sync("org-1", queue(candidate())) == {"created": 0, "updated": 1, "preserved": 0, "total": 1}
    store.decide("org-1", "CAP-ONE", "approve", "youngkwon")
    changed = candidate()
    changed["summary"] = "approval 뒤 바뀐 내용"
    assert store.sync("org-1", queue(changed))["preserved"] == 1
    assert store.get("org-1", "CAP-ONE")["summary"] != changed["summary"]


def test_restricted_capture_is_generic_and_cannot_be_approved(tmp_path: Path):
    store = CaptureRouteStore(tmp_path / "routes.json")
    secret = candidate(sensitivity="restricted")
    secret["title"] = "환자 홍길동"
    secret["summary"] = "secret-patient-value"
    store.sync("org-1", queue(secret))
    stored = store.get("org-1", "CAP-ONE")
    assert stored["title"] == "민감정보 검토 필요"
    assert "홍길동" not in str(stored)
    assert "secret-patient-value" not in str(stored)
    with pytest.raises(DispatchBlocked, match="restricted"):
        store.decide("org-1", "CAP-ONE", "approve", "youngkwon")


def test_dispatch_requires_approval_and_detects_post_approval_mutation(tmp_path: Path):
    store = CaptureRouteStore(tmp_path / "routes.json")
    store.sync("org-1", queue(candidate()))
    with pytest.raises(DispatchBlocked, match="approved"):
        dispatch_route(store, "org-1", "CAP-ONE", execute=False)
    store.decide("org-1", "CAP-ONE", "approve", "youngkwon")
    state = store.load()
    state["routesByOrg"]["org-1"][0]["summary"] = "mutated"
    store.save(state)
    with pytest.raises(DispatchBlocked, match="changed"):
        dispatch_route(store, "org-1", "CAP-ONE", execute=False)


def test_kinelo_dispatch_is_idempotent_after_success(tmp_path: Path, monkeypatch):
    store = CaptureRouteStore(tmp_path / "routes.json")
    store.sync("org-1", queue(candidate()))
    store.decide("org-1", "CAP-ONE", "approve", "youngkwon")
    monkeypatch.setenv("KINELO_OPS_INTAKE_URL", "https://ops.example/api/ops-intake")
    monkeypatch.setenv("KINELO_OPS_INTAKE_SECRET", "test-only")
    calls = []

    def fake_request(url, **kwargs):
        calls.append((url, kwargs))
        return 201, {"ok": True, "taskId": "task-1"}

    first = dispatch_route(store, "org-1", "CAP-ONE", execute=True, http_request=fake_request)
    second = dispatch_route(store, "org-1", "CAP-ONE", execute=True, http_request=fake_request)
    assert first["ok"] is True
    assert second == first
    assert len(calls) == 1
    assert calls[0][1]["payload"]["source_external_id"] == "CAP-ONE"


@pytest.mark.parametrize(
    ("destination", "repo"),
    [("physio_app", "/home/yk/physio_app"), ("second_brain", "/home/yk/brain-linux")],
)
def test_non_ops_destinations_create_bounded_mission_tasks(tmp_path: Path, monkeypatch, destination: str, repo: str):
    store = CaptureRouteStore(tmp_path / "routes.json")
    store.sync("org-1", queue(candidate(destination=destination)))
    store.decide("org-1", "CAP-ONE", "approve", "youngkwon")
    monkeypatch.setenv("MISSION_CONTROL_BASE_URL", "https://mission.example")
    calls = []

    def fake_request(url, **kwargs):
        calls.append((url, kwargs))
        if kwargs.get("method", "GET") == "GET":
            return 200, {"items": []}
        return 200, {"ok": True, "item": {"id": kwargs["payload"]["id"]}}

    result = dispatch_route(store, "org-1", "CAP-ONE", execute=True, http_request=fake_request)
    assert result["ok"] is True
    post = calls[-1]
    assert post[1]["payload"]["repo"] == repo
    assert post[1]["payload"]["status"] == "ready"
    assert "patient" not in str(post[1]["payload"]).casefold()
