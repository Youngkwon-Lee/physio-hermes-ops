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

export interface MissionControlSnapshot {
  runs: MissionRun[];
  readiness: AgentOsIntegrationReadiness[];
  heartbeatControl: AgentOsHeartbeatControlState;
}
