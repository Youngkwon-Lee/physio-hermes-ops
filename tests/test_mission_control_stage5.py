from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pytest

API_DIR = Path(__file__).resolve().parents[1] / "apps" / "api"
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

import mission_control_api
from mission_control_api import (
    apply_autonomy_policy_to_run,
    approve_next_pending_gate,
    build_base_run,
    create_mission_run,
)
from mission_control_runtime import (
    annotate_run_with_autonomy_policy,
    autonomy_policy_read_model,
    claim_mission_action,
    create_mission_action,
    evaluate_autonomy_policy,
    find_mission_action,
    load_autonomy_policy,
    next_mission_action,
    read_action_state,
    resolve_owner_agent_profiles,
    resolve_profile_id,
    update_mission_action_status,
    write_action_state,
)


def load_action_worker() -> Any:
    path = Path(__file__).resolve().parents[1] / "scripts" / "mission_control_action_worker.py"
    spec = importlib.util.spec_from_file_location("mission_control_action_worker", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_owner_agents_include_resolved_physio_profiles() -> None:
    run = build_base_run(
        title="Stage 5 owner profile smoke",
        description="Verify ownerAgents profile readback.",
        lane_id="db-data",
        owner_agents=["db", "devops", "qa"],
    )

    assert run["ownerAgents"] == ["db", "devops", "qa"]
    assert [item["profileId"] for item in run["ownerAgentProfiles"]] == [
        "physio-backend",
        "physio-orchestrator",
        "physio-qa",
    ]
    assert run["ownerAgentProfiles"][0]["routing"] == "delegated"
    assert any(item["label"] == "Hermes profiles" for item in run["artifacts"])


def test_create_mission_run_accepts_bounded_owner_agents() -> None:
    run = create_mission_run(
        {
            "organizationId": "org-1",
            "title": "Use frontend profile",
            "laneId": "feature",
            "ownerAgents": ["frontend", "unknown", "frontend", "planner"],
        }
    )

    assert run["ownerAgents"] == ["frontend", "planner"]
    assert [item["profileId"] for item in run["ownerAgentProfiles"]] == ["physio-frontend", "physio-planner"]


def test_mission_action_queue_supports_profile_prompt(tmp_path: Path) -> None:
    now = "2026-07-08T00:00:00Z"
    state_path = tmp_path / "mission_actions.json"
    state = read_action_state(state_path, now)
    organization_id, item = create_mission_action(
        {
            "organizationId": "org-1",
            "actionType": "desktop_hermes_profile_prompt",
            "title": "Ask frontend profile",
            "target": {"agent": "desktop-hermes", "host": "desktop-wsl", "profileId": "frontend"},
            "params": {"prompt": "Summarize route risk."},
        },
        now,
    )

    assert organization_id == "org-1"
    assert item["target"]["profileId"] == "physio-frontend"
    state["actionsByOrg"][organization_id] = [item]
    write_action_state(state_path, state, now)

    loaded = read_action_state(state_path, now)
    queued = next_mission_action(loaded, "org-1", "desktop-hermes", "desktop-wsl")
    assert queued and queued["id"] == item["id"]

    claimed = claim_mission_action(loaded, "org-1", item["id"], "worker-1", now)
    assert claimed["status"] == "running"
    done = update_mission_action_status(loaded, "org-1", item["id"], "done", "ok", {"ok": True}, now)
    assert done["status"] == "done"
    _, found = find_mission_action(loaded, "org-1", item["id"])
    assert found and found["resultData"] == {"ok": True}


def test_profile_id_resolver_rejects_unknown_profiles() -> None:
    assert resolve_profile_id("frontend") == "physio-frontend"
    assert resolve_profile_id("physio-qa") == "physio-qa"
    with pytest.raises(ValueError, match="unsupported profileId"):
        resolve_profile_id("default")


def test_action_worker_runs_whitelisted_profile_prompt(monkeypatch: pytest.MonkeyPatch) -> None:
    worker = load_action_worker()
    calls: list[dict[str, Any]] = []

    def fake_run_cmd(cmd: list[str], cwd: Path | None = None, timeout_sec: int = 180) -> dict[str, Any]:
        calls.append({"cmd": cmd, "cwd": cwd, "timeoutSec": timeout_sec})
        return {"cmd": " ".join(cmd), "exitCode": 0, "durationSec": 0.1, "stdout": "ok", "stderr": ""}

    monkeypatch.setattr(worker, "resolve_hermes_bin", lambda _value: "/usr/local/bin/hermes")
    monkeypatch.setattr(worker, "run_cmd", fake_run_cmd)

    result = worker.execute_desktop_hermes_profile_prompt(
        {
            "actionType": "desktop_hermes_profile_prompt",
            "target": {"profileId": "frontend"},
            "params": {"prompt": "Check UI risk.", "timeoutSec": 60},
        }
    )

    assert result["ok"] is True
    assert result["profileId"] == "physio-frontend"
    assert calls[0]["cmd"] == ["/usr/local/bin/hermes", "-p", "physio-frontend", "chat", "-q", "Check UI risk."]


def test_action_worker_rejects_unlisted_profile() -> None:
    worker = load_action_worker()
    with pytest.raises(ValueError, match="unsupported profileId"):
        worker.execute_desktop_hermes_profile_prompt(
            {
                "actionType": "desktop_hermes_profile_prompt",
                "target": {"profileId": "default"},
                "params": {"prompt": "Should not run."},
            }
        )


def test_resolved_owner_profiles_have_rows_for_runtime_agents() -> None:
    profiles = resolve_owner_agent_profiles(["orchestrator", "planner", "frontend", "backend", "db", "qa", "devops"])

    assert len(profiles) == 7
    assert {item["profileId"] for item in profiles} == {
        "physio-orchestrator",
        "physio-planner",
        "physio-frontend",
        "physio-backend",
        "physio-qa",
    }


def test_autonomy_policy_read_model_keeps_production_never() -> None:
    policy = load_autonomy_policy()
    read_model = autonomy_policy_read_model(
        policy,
        ["feature", "db-data"],
        {
            "feature": ["plan", "issue", "pull-request", "preview", "production"],
            "db-data": ["migration", "pull-request", "production"],
        },
    )

    feature = {item["gate"]: item for item in read_model["decisionsByLane"]["feature"]}
    db_data = {item["gate"]: item for item in read_model["decisionsByLane"]["db-data"]}

    assert feature["issue"]["decision"] == "auto"
    assert feature["pull-request"]["decision"] == "auto"
    assert feature["preview"]["decision"] == "manual"
    assert feature["preview"]["configuredDecision"] == "auto"
    assert feature["preview"]["requiredActuator"] == "agent-os-preview-chain"
    assert feature["production"]["decision"] == "never"
    assert db_data["production"]["decision"] == "never"
    assert db_data["migration"]["decision"] == "manual"


def test_autonomy_policy_annotates_runs_without_auto_approving_initial_manual_gate() -> None:
    run = create_mission_run(
        {
            "organizationId": "org-1",
            "title": "Autonomy policy smoke",
            "laneId": "feature",
            "ownerAgents": ["planner", "frontend", "qa"],
        }
    )

    by_gate = {item["gate"]: item for item in run["approvalItems"]}
    assert by_gate["plan"]["status"] == "pending"
    assert by_gate["plan"]["autonomy"]["decision"] == "manual"
    assert by_gate["issue"]["autonomy"]["decision"] == "auto"
    assert by_gate["pull-request"]["autonomy"]["decision"] == "auto"
    assert by_gate["preview"]["autonomy"]["decision"] == "manual"
    assert by_gate["preview"]["autonomy"]["configuredDecision"] == "auto"
    assert by_gate["production"]["autonomy"]["decision"] == "never"
    assert any(item["label"] == "Autonomy policy" for item in run["artifacts"])


def test_autonomy_policy_auto_advances_allowed_gates_after_human_plan_approval() -> None:
    run = create_mission_run(
        {
            "organizationId": "org-1",
            "title": "Autonomy policy advance",
            "laneId": "feature",
            "ownerAgents": ["planner", "frontend", "qa"],
        }
    )

    updated = apply_autonomy_policy_to_run(approve_next_pending_gate(run))
    by_gate = {item["gate"]: item for item in updated["approvalItems"]}

    assert by_gate["plan"]["status"] == "approved"
    assert by_gate["issue"]["status"] == "approved"
    assert by_gate["pull-request"]["status"] == "approved"
    assert by_gate["preview"]["status"] == "pending"
    assert by_gate["production"]["status"] == "waived"
    assert by_gate["production"]["autonomy"]["decision"] == "never"
    assert updated["status"] == "waiting-for-approval"
    assert any("auto-approved" in item["title"] for item in updated["traceItems"])


def test_autonomy_policy_auto_advances_preview_when_actuator_is_ready(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_publish_preview_deployment(run: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], str]:
        return (
            [
                {
                    "label": "Preview Deployment",
                    "kind": "preview-deploy",
                    "value": "State: READY",
                    "metadata": {"dryRun": False, "previewUrl": "https://stage5-preview.example", "state": "READY"},
                }
            ],
            [
                {
                    "id": "trace-preview-ready",
                    "timestamp": "2026-07-08T00:00:00Z",
                    "agentId": "devops",
                    "title": "Preview deployment ready",
                    "summary": "Preview is live.",
                    "tone": "success",
                }
            ],
            "ready",
        )

    monkeypatch.setattr(mission_control_api, "actuator_statuses_by_id", lambda: {"agent-os-preview-chain": "ready"})
    monkeypatch.setattr(mission_control_api, "publish_preview_deployment", fake_publish_preview_deployment)
    run = create_mission_run(
        {
            "organizationId": "org-1",
            "title": "Autonomy preview advance",
            "laneId": "feature",
            "ownerAgents": ["planner", "frontend", "qa", "devops"],
        }
    )

    updated = apply_autonomy_policy_to_run(approve_next_pending_gate(run))
    by_gate = {item["gate"]: item for item in updated["approvalItems"]}

    assert by_gate["plan"]["status"] == "approved"
    assert by_gate["issue"]["status"] == "approved"
    assert by_gate["pull-request"]["status"] == "approved"
    assert by_gate["preview"]["status"] == "approved"
    assert by_gate["preview"]["autonomy"]["decision"] == "auto"
    assert by_gate["production"]["status"] == "pending"
    assert by_gate["production"]["autonomy"]["decision"] == "never"
    assert updated["status"] == "waiting-for-approval"
    assert any(
        item.get("kind") == "preview-deploy" and not item.get("metadata", {}).get("dryRun")
        for item in updated["artifacts"]
    )


def test_autonomy_policy_file_override_is_bounded(tmp_path: Path) -> None:
    policy_path = tmp_path / "policy.json"
    policy_path.write_text(
        json.dumps(
            {
                "policyId": "test-policy",
                "version": 2,
                "defaultDecision": "auto",
                "rules": [
                    {"id": "bad-production", "laneId": "feature", "gate": "production", "decision": "auto"}
                ],
            }
        ),
        encoding="utf-8",
    )

    policy = load_autonomy_policy(policy_path)
    annotated = annotate_run_with_autonomy_policy(
        build_base_run(title="Override smoke", description="x", lane_id="feature"),
        policy,
    )

    assert evaluate_autonomy_policy(policy, "feature", "issue")["decision"] == "auto"
    assert evaluate_autonomy_policy(policy, "feature", "production")["decision"] == "never"
    assert {item["gate"]: item for item in annotated["approvalItems"]}["production"]["autonomy"]["decision"] == "never"
