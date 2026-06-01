import type { AgentId, GreenLevel } from '../../runtime/src/index';
import type { HarnessFailureClass } from './failures';

export type HarnessTraceStatus = 'queued' | 'running' | 'waiting-for-approval' | 'passed' | 'failed' | 'cancelled';
export type WorkerLifecycleState =
  | 'spawning'
  | 'trust_required'
  | 'ready_for_prompt'
  | 'prompt_accepted'
  | 'running'
  | 'blocked'
  | 'finished'
  | 'failed';

export interface HarnessTraceEvent {
  id: string;
  runId: string;
  agentId: AgentId;
  status: HarnessTraceStatus;
  title: string;
  summary: string;
  createdAt: string;
  artifactHref?: string;
  failureClass?: HarnessFailureClass;
  greenLevel?: GreenLevel;
  workerState?: WorkerLifecycleState;
}

export const TRACE_EVENT_TYPES = [
  'mission.received',
  'plan.created',
  'approval.requested',
  'branch.created',
  'checks.started',
  'checks.completed',
  'pr.created',
  'preview.created',
  'deploy.approved',
  'harness.improvement.proposed',
  'worker.state.changed',
  'failure.classified',
  'green_level.updated',
] as const;

export type TraceEventType = (typeof TRACE_EVENT_TYPES)[number];
