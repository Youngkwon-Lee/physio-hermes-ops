import { AGENT_PROFILES, type AgentId } from './agents';

export interface WorkflowAgentSelection {
  owner: AgentId;
}

export interface PermissionProfileLike {
  agentId: AgentId;
  writable: string[];
  approvalRequired: string[];
  checks: string[];
}

export interface MissionDraftInput {
  title: string;
  description: string;
  workflowId: string;
  requestedAgents?: AgentId[];
}

export interface MissionRunPlan {
  title: string;
  description: string;
  workflowId: string;
  agents: Array<{
    id: AgentId;
    name: string;
    role: string;
    writable: string[];
    approvalRequired: string[];
    checks: string[];
  }>;
  approvalGates: string[];
}

export function createMissionRunPlan(params: {
  input: MissionDraftInput;
  workflowAgents: WorkflowAgentSelection[];
  permissionProfiles: PermissionProfileLike[];
}): MissionRunPlan {
  const selectedAgentIds = Array.from(new Set(
    params.input.requestedAgents?.length
      ? params.input.requestedAgents
      : params.workflowAgents.map((step) => step.owner),
  ));

  const agents = selectedAgentIds.flatMap((agentId) => {
    const profile = AGENT_PROFILES.find((agent) => agent.id === agentId);
    const permissionProfile = params.permissionProfiles.find((candidate) => candidate.agentId === agentId);
    if (!profile || !permissionProfile) return [];

    return {
      id: profile.id,
      name: profile.name,
      role: profile.role,
      writable: permissionProfile.writable,
      approvalRequired: permissionProfile.approvalRequired,
      checks: permissionProfile.checks,
    };
  });

  return {
    title: params.input.title,
    description: params.input.description,
    workflowId: params.input.workflowId,
    agents,
    approvalGates: Array.from(new Set(agents.flatMap((agent) => agent.approvalRequired))),
  };
}
