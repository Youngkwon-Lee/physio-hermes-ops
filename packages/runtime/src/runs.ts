import { AGENT_PROFILES, type AgentId, type ApprovalGate } from './agents';
import { getCompanyLane, type CompanyLaneId } from './lanes';
import type { MissionArtifact, WorkflowId } from './contracts';

export type MissionRunStatus =
  | 'intake'
  | 'planning'
  | 'waiting-for-approval'
  | 'building'
  | 'reviewing'
  | 'deploying'
  | 'completed'
  | 'blocked';

export type MissionPriority = 'low' | 'medium' | 'high' | 'urgent';
export type ApprovalStatus = 'pending' | 'approved' | 'rejected' | 'waived';
export type TraceTone = 'neutral' | 'success' | 'warning' | 'danger';

export interface MissionTraceItem {
  id: string;
  timestamp: string;
  agentId: AgentId;
  title: string;
  summary: string;
  tone: TraceTone;
}

export interface MissionApprovalItem {
  id: string;
  gate: ApprovalGate;
  label: string;
  status: ApprovalStatus;
  requiredBy: AgentId;
}

export interface MissionRunSource {
  streamId: string;
  channelId?: string;
  threadId?: string;
  channelName?: string;
  threadName?: string;
}

export interface MissionRun {
  id: string;
  title: string;
  description: string;
  laneId: CompanyLaneId;
  status: MissionRunStatus;
  priority: MissionPriority;
  workflowIds: WorkflowId[];
  ownerAgents: AgentId[];
  approvalItems: MissionApprovalItem[];
  traceItems: MissionTraceItem[];
  artifacts: MissionArtifact[];
  source?: MissionRunSource;
  createdAt: string;
  updatedAt: string;
}

export interface CreateMissionRunInput {
  title: string;
  description: string;
  laneId: CompanyLaneId;
  priority?: MissionPriority;
  source?: MissionRunSource;
}

function compactId(seed: string) {
  return seed
    .toLowerCase()
    .replace(/[^a-z0-9가-힣]+/g, '-')
    .replace(/^-|-$/g, '')
    .slice(0, 36) || 'mission';
}

function uniqueId(prefix: string) {
  return `${prefix}_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 7)}`;
}

function approvalLabel(gate: ApprovalGate) {
  const labels: Record<ApprovalGate, string> = {
    plan: 'Approve plan',
    issue: 'Create issues',
    'pull-request': 'Approve PR',
    migration: 'Approve migration',
    preview: 'Approve preview',
    production: 'Approve deploy',
  };

  return labels[gate];
}

function defaultApprovalAgent(gate: ApprovalGate): AgentId {
  if (gate === 'migration') return 'db';
  if (gate === 'preview' || gate === 'production') return 'devops';
  if (gate === 'pull-request') return 'qa';
  return 'orchestrator';
}

export function createMissionRunDraft(input: CreateMissionRunInput): MissionRun {
  const lane = getCompanyLane(input.laneId);
  if (!lane) {
    throw new Error(`Unknown company lane: ${input.laneId}`);
  }

  const now = new Date().toISOString();
  const id = uniqueId(compactId(input.title));
  const firstGate = lane.approvalGates[0];
  const firstApprovalLabel = firstGate ? approvalLabel(firstGate) : 'Approval';

  return {
    id,
    title: input.title,
    description: input.description,
    laneId: lane.id,
    status: 'waiting-for-approval',
    priority: input.priority ?? 'medium',
    workflowIds: lane.defaultWorkflowIds,
    ownerAgents: lane.primaryAgents,
    approvalItems: lane.approvalGates.map((gate, index) => ({
      id: `${id}_${gate}`,
      gate,
      label: approvalLabel(gate),
      status: index === 0 ? 'pending' : 'waived',
      requiredBy: defaultApprovalAgent(gate),
    })),
    traceItems: [
      {
        id: `${id}_mission_received`,
        timestamp: now,
        agentId: 'orchestrator',
        title: 'Mission received',
        summary: `${lane.name} selected with ${lane.defaultGreenLevel} green-level target.`,
        tone: 'neutral',
      },
      {
        id: `${id}_approval_requested`,
        timestamp: now,
        agentId: 'planner',
        title: `${firstApprovalLabel} requested`,
        summary: `${firstApprovalLabel} is blocked until a human clicks approve.`,
        tone: 'warning',
      },
    ],
    artifacts: [
      { label: 'Lane', value: lane.name },
      { label: 'Target green level', value: lane.defaultGreenLevel },
      {
        label: 'Primary agents',
        value: lane.primaryAgents.map((agentId) => (
          AGENT_PROFILES.find((agent) => agent.id === agentId)?.label ?? agentId
        )).join(', '),
      },
      ...(input.source?.streamId ? [{ label: 'Source stream', value: input.source.streamId }] : []),
      ...(input.source?.threadName ? [{ label: 'Source thread', value: input.source.threadName }] : []),
      ...(input.source?.channelName ? [{ label: 'Source channel', value: input.source.channelName }] : []),
    ],
    source: input.source,
    createdAt: now,
    updatedAt: now,
  };
}

export function approveNextPendingGate(run: MissionRun): MissionRun {
  const pendingApproval = run.approvalItems.find((item) => item.status === 'pending');
  if (!pendingApproval) {
    return run;
  }

  const now = new Date().toISOString();
  const pendingIndex = run.approvalItems.findIndex((item) => item.id === pendingApproval.id);
  const nextApproval = run.approvalItems[pendingIndex + 1];
  const approvalItems = run.approvalItems.map((item) => {
    if (item.id === pendingApproval.id) {
      return { ...item, status: 'approved' as const };
    }

    if (nextApproval && item.id === nextApproval.id) {
      return { ...item, status: 'pending' as const };
    }

    return item;
  });

  const nextPending = approvalItems.find((item) => item.status === 'pending');

  return {
    ...run,
    status: nextPending ? 'waiting-for-approval' : 'completed',
    approvalItems,
    traceItems: [
      ...run.traceItems,
      {
        id: `${run.id}_${pendingApproval.gate}_approved_${Date.now().toString(36)}`,
        timestamp: now,
        agentId: pendingApproval.requiredBy,
        title: `${pendingApproval.label} approved`,
        summary: nextPending
          ? `${nextPending.label} is now the next human gate.`
          : 'All human gates for this mock run are complete.',
        tone: 'success',
      },
    ],
    updatedAt: now,
  };
}

export function rejectNextPendingGate(run: MissionRun): MissionRun {
  const pendingApproval = run.approvalItems.find((item) => item.status === 'pending');
  if (!pendingApproval) {
    return run;
  }

  const now = new Date().toISOString();

  return {
    ...run,
    status: 'blocked',
    approvalItems: run.approvalItems.map((item) => (
      item.id === pendingApproval.id ? { ...item, status: 'rejected' as const } : item
    )),
    traceItems: [
      ...run.traceItems,
      {
        id: `${run.id}_${pendingApproval.gate}_rejected_${Date.now().toString(36)}`,
        timestamp: now,
        agentId: pendingApproval.requiredBy,
        title: `${pendingApproval.label} rejected`,
        summary: 'Run is blocked and must return to the owner agent with requested changes.',
        tone: 'danger',
      },
    ],
    updatedAt: now,
  };
}
