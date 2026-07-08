from __future__ import annotations

import uuid
from copy import deepcopy
from pathlib import Path
from typing import Any


ACTION_TYPES = {
    "desktop_hermes_prompt",
    "desktop_hermes_profile_prompt",
    "desktop_repo_sync_restart_smoke",
}
ACTION_STATUSES = {"queued", "running", "done", "failed", "blocked", "cancelled"}
AUTONOMY_DECISIONS = {"auto", "manual", "never"}

DEFAULT_AUTONOMY_POLICY: dict[str, Any] = {
    "policyId": "aiops-autonomy-policy-v1",
    "version": 1,
    "description": "Lane and gate policy for Product Mission Control autonomous approvals.",
    "defaultDecision": "manual",
    "rules": [
        {
            "id": "production-never",
            "laneId": "*",
            "gate": "production",
            "decision": "never",
            "reason": "Production is a permanent human approval boundary.",
        },
        {
            "id": "feature-issue-auto",
            "laneId": "feature",
            "gate": "issue",
            "decision": "auto",
            "reason": "Approved feature plans may open issue drafts automatically.",
        },
        {
            "id": "feature-pr-auto",
            "laneId": "feature",
            "gate": "pull-request",
            "decision": "auto",
            "reason": "Approved feature issue plans may prepare draft PR payloads automatically.",
        },
        {
            "id": "growth-issue-auto",
            "laneId": "growth",
            "gate": "issue",
            "decision": "auto",
            "reason": "Approved growth plans may open issue drafts automatically.",
        },
        {
            "id": "growth-pr-auto",
            "laneId": "growth",
            "gate": "pull-request",
            "decision": "auto",
            "reason": "Approved growth issue plans may prepare draft PR payloads automatically.",
        },
        {
            "id": "maintenance-pr-auto",
            "laneId": "maintenance",
            "gate": "pull-request",
            "decision": "auto",
            "reason": "Maintenance fixes may prepare draft PR payloads after queue intake.",
        },
        {
            "id": "mlops-pr-auto",
            "laneId": "mlops",
            "gate": "pull-request",
            "decision": "auto",
            "reason": "MLOps improvements may prepare draft PR payloads after plan approval.",
        },
        {
            "id": "ops-finance-issue-auto",
            "laneId": "ops-finance",
            "gate": "issue",
            "decision": "auto",
            "reason": "Approved ops plans may open follow-up issue drafts automatically.",
        },
    ],
}

CORE_PROFILE_IDS = {
    "physio-orchestrator",
    "physio-planner",
    "physio-frontend",
    "physio-backend",
    "physio-qa",
}

AGENT_PROFILE_ROWS: tuple[dict[str, str], ...] = (
    {
        "agentId": "orchestrator",
        "profileId": "physio-orchestrator",
        "profileLabel": "Physio Orchestrator",
        "role": "전체 작업을 분해하고 승인 경계를 조율한다.",
        "routing": "direct",
    },
    {
        "agentId": "planner",
        "profileId": "physio-planner",
        "profileLabel": "Physio Planner",
        "role": "목표를 PRD, acceptance criteria, issue로 바꾼다.",
        "routing": "direct",
    },
    {
        "agentId": "frontend",
        "profileId": "physio-frontend",
        "profileLabel": "Physio Frontend",
        "role": "UI 구현과 브라우저 검증을 담당한다.",
        "routing": "direct",
    },
    {
        "agentId": "backend",
        "profileId": "physio-backend",
        "profileLabel": "Physio Backend",
        "role": "API, domain logic, server 검증을 담당한다.",
        "routing": "direct",
    },
    {
        "agentId": "db",
        "profileId": "physio-backend",
        "profileLabel": "Physio Backend",
        "role": "DB/RLS 작업은 dedicated DB profile 전까지 backend profile에 위임한다.",
        "routing": "delegated",
    },
    {
        "agentId": "qa",
        "profileId": "physio-qa",
        "profileLabel": "Physio QA",
        "role": "테스트, 회귀검사, release risk를 담당한다.",
        "routing": "direct",
    },
    {
        "agentId": "devops",
        "profileId": "physio-orchestrator",
        "profileLabel": "Physio Orchestrator",
        "role": "DevOps 작업은 dedicated DevOps profile 전까지 orchestrator profile에 위임한다.",
        "routing": "delegated",
    },
)

PROFILE_BY_AGENT = {row["agentId"]: row for row in AGENT_PROFILE_ROWS}


def normalized_policy_decision(value: Any, default: str = "manual") -> str:
    decision = str(value or "").strip()
    if decision in AUTONOMY_DECISIONS:
        return decision
    return default


def normalize_autonomy_policy(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        value = deepcopy(DEFAULT_AUTONOMY_POLICY)
    policy_id = str(value.get("policyId") or DEFAULT_AUTONOMY_POLICY["policyId"]).strip()
    default_decision = normalized_policy_decision(value.get("defaultDecision"), "manual")
    rules: list[dict[str, str]] = []
    for raw_rule in value.get("rules", []):
        if not isinstance(raw_rule, dict):
            continue
        lane_id = str(raw_rule.get("laneId") or "*").strip() or "*"
        gate = str(raw_rule.get("gate") or "").strip()
        decision = normalized_policy_decision(raw_rule.get("decision"), default_decision)
        if not gate:
            continue
        rules.append(
            {
                "id": str(raw_rule.get("id") or f"{lane_id}:{gate}:{decision}").strip(),
                "laneId": lane_id,
                "gate": gate,
                "decision": decision,
                "reason": str(raw_rule.get("reason") or "").strip(),
            }
        )
    if not any(rule["gate"] == "production" and rule["decision"] == "never" for rule in rules):
        rules.insert(0, deepcopy(DEFAULT_AUTONOMY_POLICY["rules"][0]))
    return {
        "policyId": policy_id,
        "version": int(value.get("version") or DEFAULT_AUTONOMY_POLICY["version"]),
        "description": str(value.get("description") or DEFAULT_AUTONOMY_POLICY["description"]).strip(),
        "defaultDecision": default_decision,
        "rules": rules,
    }


def load_autonomy_policy(path: Path | None = None) -> dict[str, Any]:
    if path and path.exists():
        try:
            import json

            return normalize_autonomy_policy(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            return normalize_autonomy_policy(DEFAULT_AUTONOMY_POLICY)
    return normalize_autonomy_policy(DEFAULT_AUTONOMY_POLICY)


def rule_specificity(rule: dict[str, str], lane_id: str, gate: str) -> int:
    score = 0
    if rule.get("laneId") == lane_id:
        score += 2
    elif rule.get("laneId") == "*":
        score += 1
    if rule.get("gate") == gate:
        score += 2
    return score


def evaluate_autonomy_policy(policy: dict[str, Any], lane_id: str, gate: str) -> dict[str, Any]:
    normalized = normalize_autonomy_policy(policy)
    if gate == "production":
        return {
            "policyId": normalized["policyId"],
            "ruleId": "production-never",
            "decision": "never",
            "requiresHuman": True,
            "reason": "Production is a permanent human approval boundary.",
        }

    candidates = [
        rule
        for rule in normalized["rules"]
        if rule.get("gate") == gate and rule.get("laneId") in {lane_id, "*"}
    ]
    candidates.sort(key=lambda rule: rule_specificity(rule, lane_id, gate), reverse=True)
    rule = candidates[0] if candidates else None
    decision = rule["decision"] if rule else normalized["defaultDecision"]
    return {
        "policyId": normalized["policyId"],
        "ruleId": rule["id"] if rule else "default",
        "decision": decision,
        "requiresHuman": decision != "auto",
        "reason": rule["reason"] if rule else "No explicit lane/gate rule matched.",
    }


def annotate_run_with_autonomy_policy(run: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    updated = deepcopy(run)
    lane_id = str(updated.get("laneId") or "").strip()
    decisions: list[str] = []
    for item in updated.get("approvalItems", []):
        if not isinstance(item, dict):
            continue
        gate = str(item.get("gate") or "").strip()
        evaluation = evaluate_autonomy_policy(policy, lane_id, gate)
        item["autonomy"] = evaluation
        decisions.append(f"{gate}:{evaluation['decision']}")

    artifact = {
        "label": "Autonomy policy",
        "kind": "policy",
        "value": ", ".join(decisions),
        "metadata": {
            "policyId": normalize_autonomy_policy(policy)["policyId"],
            "production": "never",
        },
    }
    artifacts = updated.setdefault("artifacts", [])
    for index, current in enumerate(artifacts):
        if isinstance(current, dict) and current.get("label") == artifact["label"] and current.get("kind") == artifact["kind"]:
            artifacts[index] = artifact
            break
    else:
        artifacts.append(artifact)
    return updated


def autonomy_policy_read_model(policy: dict[str, Any], lane_ids: list[str], gates_by_lane: dict[str, list[str]]) -> dict[str, Any]:
    normalized = normalize_autonomy_policy(policy)
    decisions_by_lane: dict[str, list[dict[str, Any]]] = {}
    for lane_id in lane_ids:
        decisions_by_lane[lane_id] = [
            {"gate": gate, **evaluate_autonomy_policy(normalized, lane_id, gate)}
            for gate in gates_by_lane.get(lane_id, [])
        ]
    return {
        "policyId": normalized["policyId"],
        "version": normalized["version"],
        "description": normalized["description"],
        "defaultDecision": normalized["defaultDecision"],
        "rules": normalized["rules"],
        "decisionsByLane": decisions_by_lane,
    }


def normalize_owner_agent_ids(values: Any, fallback: list[str]) -> list[str]:
    if not isinstance(values, list):
        values = fallback
    seen: set[str] = set()
    agents: list[str] = []
    for item in values:
        agent_id = str(item).strip()
        if not agent_id or agent_id not in PROFILE_BY_AGENT or agent_id in seen:
            continue
        agents.append(agent_id)
        seen.add(agent_id)
    return agents or list(fallback)


def resolve_owner_agent_profiles(owner_agents: list[str]) -> list[dict[str, str]]:
    profiles: list[dict[str, str]] = []
    for agent_id in owner_agents:
        row = PROFILE_BY_AGENT.get(agent_id)
        if row:
            profiles.append(dict(row))
    return profiles


def resolve_profile_id(value: Any) -> str:
    profile_id = str(value or "").strip()
    if profile_id in CORE_PROFILE_IDS:
        return profile_id
    row = PROFILE_BY_AGENT.get(profile_id)
    if row:
        return row["profileId"]
    raise ValueError(f"unsupported profileId: {profile_id or 'missing'}")


def base_action_state(now: str) -> dict[str, Any]:
    return {"version": 1, "updatedAt": now, "actionsByOrg": {}}


def ensure_action_state_shape(state: Any, now: str) -> dict[str, Any]:
    if not isinstance(state, dict):
        return base_action_state(now)
    if not isinstance(state.get("actionsByOrg"), dict):
        state["actionsByOrg"] = {}
    if "version" not in state:
        state["version"] = 1
    if "updatedAt" not in state:
        state["updatedAt"] = now
    return state


def read_action_state(path: Path, now: str) -> dict[str, Any]:
    if not path.exists():
        return base_action_state(now)
    try:
        import json

        return ensure_action_state_shape(json.loads(path.read_text(encoding="utf-8")), now)
    except (OSError, ValueError):
        return base_action_state(now)


def write_action_state(path: Path, state: dict[str, Any], now: str) -> None:
    import json

    path.parent.mkdir(parents=True, exist_ok=True)
    state["updatedAt"] = now
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def create_mission_action(payload: dict[str, Any], now: str) -> tuple[str, dict[str, Any]]:
    organization_id = str(payload.get("organizationId") or "").strip()
    if not organization_id:
        raise ValueError("organizationId is required")

    action_type = str(payload.get("actionType") or "").strip()
    if action_type not in ACTION_TYPES:
        raise ValueError("actionType is invalid")

    title = str(payload.get("title") or action_type).strip() or action_type
    target = payload.get("target") if isinstance(payload.get("target"), dict) else {}
    params = payload.get("params") if isinstance(payload.get("params"), dict) else {}
    profile_id = None
    if action_type == "desktop_hermes_profile_prompt":
        profile_id = resolve_profile_id(params.get("profileId") or target.get("profileId") or target.get("agent"))

    item = {
        "id": str(payload.get("id") or f"action-{uuid.uuid4()}").strip(),
        "actionType": action_type,
        "title": title,
        "status": "queued",
        "priority": int(payload.get("priority") or 50),
        "target": {
            "agent": str(target.get("agent") or "desktop-hermes").strip() or "desktop-hermes",
            "surface": str(target.get("surface") or "hermes-gateway").strip() or "hermes-gateway",
            "host": str(target.get("host") or "desktop-wsl").strip() or "desktop-wsl",
            "profileId": profile_id,
        },
        "repo": str(payload.get("repo") or "").strip() or None,
        "params": deepcopy(params),
        "sourceThread": deepcopy(payload.get("sourceThread") if isinstance(payload.get("sourceThread"), dict) else {}),
        "createdAt": now,
        "updatedAt": now,
        "claimedAt": None,
        "completedAt": None,
        "workerId": None,
        "result": None,
        "resultData": None,
    }
    if profile_id:
        item["params"]["profileId"] = profile_id
    return organization_id, item


def action_rows(state: dict[str, Any], organization_id: str) -> list[dict[str, Any]]:
    rows = state.setdefault("actionsByOrg", {}).setdefault(organization_id, [])
    if not isinstance(rows, list):
        rows = []
        state["actionsByOrg"][organization_id] = rows
    return rows


def list_mission_actions(state: dict[str, Any], organization_id: str, limit: int) -> list[dict[str, Any]]:
    rows = [row for row in action_rows(state, organization_id) if isinstance(row, dict)]
    rows.sort(key=lambda row: (int(row.get("priority") or 50), str(row.get("createdAt") or "")))
    return rows[: max(1, limit)]


def find_mission_action(state: dict[str, Any], organization_id: str, action_id: str) -> tuple[int, dict[str, Any] | None]:
    rows = action_rows(state, organization_id)
    for index, row in enumerate(rows):
        if isinstance(row, dict) and str(row.get("id") or "") == action_id:
            return index, row
    return -1, None


def next_mission_action(state: dict[str, Any], organization_id: str, target_agent: str, target_host: str | None) -> dict[str, Any] | None:
    for item in list_mission_actions(state, organization_id, 100):
        target = item.get("target") if isinstance(item.get("target"), dict) else {}
        if item.get("status") != "queued":
            continue
        if target_agent and str(target.get("agent") or "") != target_agent:
            continue
        if target_host and str(target.get("host") or "") != target_host:
            continue
        return item
    return None


def claim_mission_action(state: dict[str, Any], organization_id: str, action_id: str, worker_id: str, now: str) -> dict[str, Any]:
    index, item = find_mission_action(state, organization_id, action_id)
    if item is None:
        raise KeyError("Mission action not found")
    if item.get("status") not in {"queued", "running"}:
        raise ValueError("Mission action is not claimable")
    updated = {**item, "status": "running", "claimedAt": now, "updatedAt": now, "workerId": worker_id}
    action_rows(state, organization_id)[index] = updated
    return updated


def update_mission_action_status(
    state: dict[str, Any],
    organization_id: str,
    action_id: str,
    status: str,
    result: str | None,
    result_data: Any,
    now: str,
) -> dict[str, Any]:
    if status not in ACTION_STATUSES:
        raise ValueError("status is invalid")
    index, item = find_mission_action(state, organization_id, action_id)
    if item is None:
        raise KeyError("Mission action not found")
    updated = {
        **item,
        "status": status,
        "updatedAt": now,
        "completedAt": now if status in {"done", "failed", "blocked", "cancelled"} else item.get("completedAt"),
        "result": result,
        "resultData": result_data,
    }
    action_rows(state, organization_id)[index] = updated
    return updated
