import type {
  CompanyLaneId,
  MissionPriority,
  MissionRun,
  MissionRunSource,
} from '../../runtime/src/index';

export type AgentOsIntegrationStatus = 'ready' | 'dry-run' | 'blocked';
export type AgentOsIntegrationProbeStatus = 'pass' | 'warn' | 'fail';

export interface AgentOsIntegrationReadiness {
  id: string;
  label: string;
  status: AgentOsIntegrationStatus;
  mode: string;
  summary: string;
  requiredEnv: string[];
  missingEnv: string[];
}

export interface AgentOsIntegrationProbe {
  id: string;
  label: string;
  status: AgentOsIntegrationProbeStatus;
  summary: string;
  detail: string;
  checkedAt: string;
  latencyMs: number | null;
}

export interface AgentOsIntegrationHealthReport {
  checkedAt: string;
  probes: AgentOsIntegrationProbe[];
  totals: {
    pass: number;
    warn: number;
    fail: number;
  };
}

export interface AgentOsHeartbeatResult {
  mode: 'read-only' | 'trace-writing';
  checkedRuns: number;
  pendingApprovals: number;
  heartbeatTraces: number;
  staleRuns: Array<{
    runId: string;
    title: string;
    status: string;
    pendingGate: string;
    ageMinutes: number;
  }>;
  integrations: {
    ready: number;
    dryRun: number;
    blocked: number;
  };
}

export interface AgentOsHeartbeatControlState {
  armed: boolean;
  mode: 'manual-only' | 'cron-armed';
  summary: string;
  requiredEnv: string[];
  missingEnv: string[];
  cronSchedule: string;
}

export interface ListMissionRunsInput {
  organizationId: string;
  limit?: number;
}

export interface CreateMissionRunInput {
  organizationId: string;
  title: string;
  description?: string;
  laneId: CompanyLaneId;
  priority?: MissionPriority;
  source?: MissionRunSource;
}

export interface MissionRunGateInput {
  organizationId: string;
  runId: string;
}

export interface DailyOpsRunInput {
  organizationId: string;
}

export interface IntegrationHealthInput {
  organizationId: string;
}

export interface HeartbeatCronRequestInput {
  organizationId: string;
}

export interface A2aLiteConversationCallbackStatus {
  attempted: boolean;
  ok: boolean;
  statusCode: number | null;
  url?: string | null;
  error?: string | null;
}

export interface A2aLiteConversationMessagePreview {
  timestamp?: string | null;
  text?: string | null;
}

export interface A2aLiteConversationSummary {
  conversationId: string;
  state: string;
  updatedAt: string;
  latestRole?: string | null;
  latestMessageId?: string | null;
  latestReplyTo?: string | null;
  goal?: string | null;
  summary: string;
  from: {
    agent?: string | null;
    surface?: string | null;
    host?: string | null;
  };
  to: {
    agent?: string | null;
    surface?: string | null;
    host?: string | null;
  };
  context: {
    repo?: string | null;
    branch?: string | null;
    threadId?: string | null;
  };
  callback?: A2aLiteConversationCallbackStatus | null;
  counts: {
    payloads: number;
    messageRows: number;
    inbound: number;
    outbound: number;
    autoActions: number;
  };
  latestRequestText?: string | null;
  latestAnswerText?: string | null;
  lastQuestion?: A2aLiteConversationMessagePreview | null;
  lastResult?: A2aLiteConversationMessagePreview | null;
  reportPath?: string | null;
  linkedRunIds: string[];
}

export type HandoffInboxStatus = 'waiting_for_codex' | 'in_progress' | 'needs_reply' | 'done' | 'blocked';

export interface HandoffInboxParty {
  agent: string;
  surface: string;
  host?: string | null;
}

export interface HandoffInboxSourceThread {
  channelId?: string | null;
  threadId?: string | null;
  channelName?: string | null;
  threadName?: string | null;
  url?: string | null;
}

export interface HandoffInboxItem {
  id: string;
  kind: string;
  status: HandoffInboxStatus;
  createdAt: string;
  updatedAt: string;
  from: HandoffInboxParty;
  to: HandoffInboxParty;
  repo?: string | null;
  goal: string;
  context?: string | null;
  expectedOutput?: string | null;
  sourceThread: HandoffInboxSourceThread;
  result?: string | null;
  linkedRunId?: string | null;
  linkedConversationId?: string | null;
  tags: string[];
}

export interface CreateHandoffInboxItemInput {
  organizationId: string;
  id?: string;
  handoffId?: string;
  kind?: string;
  status?: HandoffInboxStatus;
  from?: Partial<HandoffInboxParty>;
  to?: Partial<HandoffInboxParty>;
  repo?: string;
  goal: string;
  context?: string;
  expectedOutput?: string;
  sourceThread?: HandoffInboxSourceThread;
  result?: string;
  linkedRunId?: string;
  linkedConversationId?: string;
  tags?: string[];
}

export interface UpdateHandoffInboxStatusInput {
  organizationId: string;
  handoffId: string;
  status: HandoffInboxStatus;
  result?: string;
}

export interface MissionControlSnapshot {
  runs: MissionRun[];
  a2aLiteConversations: A2aLiteConversationSummary[];
  handoffs: HandoffInboxItem[];
  readiness: AgentOsIntegrationReadiness[];
  heartbeatControl: AgentOsHeartbeatControlState;
}
