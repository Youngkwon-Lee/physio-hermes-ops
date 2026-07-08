from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

import pytest

API_DIR = Path(__file__).resolve().parents[1] / "apps" / "api"
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

from mission_control_api import build_base_run, create_mission_run
from mission_control_runtime import (
    claim_mission_action,
    create_mission_action,
    find_mission_action,
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
