export type HarnessFailureClass =
  | 'prompt_delivery'
  | 'trust_gate'
  | 'branch_divergence'
  | 'compile'
  | 'test'
  | 'plugin_startup'
  | 'mcp_startup'
  | 'mcp_handshake'
  | 'gateway_routing'
  | 'tool_runtime'
  | 'permission_boundary'
  | 'approval_missing'
  | 'db_rls'
  | 'preview_deploy'
  | 'infra'
  | 'unknown';

export interface HarnessFailurePattern {
  id: HarnessFailureClass;
  label: string;
  firstRecovery: string;
  escalatesToHuman: boolean;
}

export const HARNESS_FAILURE_PATTERNS: HarnessFailurePattern[] = [
  {
    id: 'prompt_delivery',
    label: 'Prompt delivery failed',
    firstRecovery: 'Retry once after worker ready_for_prompt state is observed.',
    escalatesToHuman: false,
  },
  {
    id: 'trust_gate',
    label: 'Worker trust gate',
    firstRecovery: 'Resolve only for allowlisted repo/worktree; otherwise request human approval.',
    escalatesToHuman: true,
  },
  {
    id: 'branch_divergence',
    label: 'Branch stale against main',
    firstRecovery: 'Refresh branch before broad verification and classify failures again.',
    escalatesToHuman: false,
  },
  {
    id: 'compile',
    label: 'Compile or typecheck failure',
    firstRecovery: 'Return to implementation owner with the smallest failing command and changed-file scope.',
    escalatesToHuman: false,
  },
  {
    id: 'test',
    label: 'Test failure',
    firstRecovery: 'Run targeted failing test once, then ask QA to classify product regression vs brittle test.',
    escalatesToHuman: false,
  },
  {
    id: 'plugin_startup',
    label: 'Plugin startup failure',
    firstRecovery: 'Restart plugin once and record degraded-mode status if only optional tools failed.',
    escalatesToHuman: false,
  },
  {
    id: 'mcp_startup',
    label: 'MCP startup failure',
    firstRecovery: 'Retry MCP server startup once and classify config, transport, or auth.',
    escalatesToHuman: false,
  },
  {
    id: 'mcp_handshake',
    label: 'MCP handshake failure',
    firstRecovery: 'Reconnect once, then mark the dependent tool lane blocked.',
    escalatesToHuman: false,
  },
  {
    id: 'gateway_routing',
    label: 'Model or gateway routing failure',
    firstRecovery: 'Retry through configured fallback provider when capability policy allows it.',
    escalatesToHuman: false,
  },
  {
    id: 'tool_runtime',
    label: 'Tool runtime failure',
    firstRecovery: 'Capture structured input/output/error and retry only if the tool is idempotent.',
    escalatesToHuman: false,
  },
  {
    id: 'permission_boundary',
    label: 'Permission boundary violation',
    firstRecovery: 'Stop the lane and request approval or reroute to the correct agent harness.',
    escalatesToHuman: true,
  },
  {
    id: 'approval_missing',
    label: 'Required approval missing',
    firstRecovery: 'Pause the workflow and emit a human approval request.',
    escalatesToHuman: true,
  },
  {
    id: 'db_rls',
    label: 'Database or RLS boundary risk',
    firstRecovery: 'Route to DB Agent and require RLS verification checklist before PR approval.',
    escalatesToHuman: true,
  },
  {
    id: 'preview_deploy',
    label: 'Preview deploy or smoke failure',
    firstRecovery: 'Keep production locked, attach preview logs, and rerun smoke once after fix.',
    escalatesToHuman: true,
  },
  {
    id: 'infra',
    label: 'Infrastructure failure',
    firstRecovery: 'Retry once if transient; otherwise create incident note with owner and blast radius.',
    escalatesToHuman: true,
  },
  {
    id: 'unknown',
    label: 'Unknown failure',
    firstRecovery: 'Capture logs and require QA classification before continuing.',
    escalatesToHuman: true,
  },
];

export function getHarnessFailurePattern(failureClass: HarnessFailureClass) {
  return HARNESS_FAILURE_PATTERNS.find((pattern) => pattern.id === failureClass);
}
