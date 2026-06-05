import type { MissionArtifact, MissionRun } from '../../runtime/src/index';

export const CODEX_BRIDGE_DEFAULT_HOST = 'macbook';
export const CODEX_BRIDGE_DEFAULT_BINARY = '/Applications/Codex.app/Contents/Resources/codex';
export const CODEX_BRIDGE_DEFAULT_WORKDIR = '~/tmp/codex-smoke';

export type CodexBridgePermissionStage =
  | 'health'
  | 'read_only'
  | 'workspace_write'
  | 'checks'
  | 'draft_pr';

export type CodexBridgeTaskStatus =
  | 'queued'
  | 'running'
  | 'passed'
  | 'failed'
  | 'blocked';

export type CodexBridgeFailureClass =
  | 'transport_failure'
  | 'binary_failure'
  | 'runtime_auth_failure'
  | 'exec_failure'
  | 'artifact_failure';

export interface CodexBridgeTask {
  id: string;
  runId: string;
  targetHost: string;
  codexBinary: string;
  workdir: string;
  permissionStage: CodexBridgePermissionStage;
  sandbox: 'read-only' | 'workspace-write' | 'danger-full-access';
  prompt: string;
  status: CodexBridgeTaskStatus;
  jsonOut?: string;
}

export interface CodexBridgeSmokeStep {
  name: string;
  passed: boolean;
  failureClass: CodexBridgeFailureClass;
  exitCode: number | null;
  durationMs: number;
  stdout: string;
  stderr: string;
}

export interface CodexRemoteSmokeResult {
  schema: 'codex_remote_smoke_v0_1';
  status: 'pass' | 'fail';
  target: {
    host: string;
    codex: string;
    workdir: string;
    healthOnly: boolean;
  };
  expected: string;
  failure: {
    class: CodexBridgeFailureClass;
    message: string;
    hint?: string;
  } | null;
  steps: CodexBridgeSmokeStep[];
}

function compactId(value: string) {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9가-힣]+/g, '-')
    .replace(/^-|-$/g, '')
    .slice(0, 42) || 'codex-bridge';
}

function formatStep(step: CodexBridgeSmokeStep) {
  const status = step.passed ? 'PASS' : 'FAIL';
  return `- ${step.name}: ${status} (${step.durationMs}ms, ${step.failureClass})`;
}

function smokeSummary(result: CodexRemoteSmokeResult) {
  return [
    `Status: ${result.status}`,
    `Host: ${result.target.host}`,
    `Codex: ${result.target.codex}`,
    `Workdir: ${result.target.workdir}`,
    `Health only: ${result.target.healthOnly ? 'yes' : 'no'}`,
    '',
    'Steps:',
    ...result.steps.map(formatStep),
    ...(result.failure
      ? [
          '',
          'Failure:',
          `- class: ${result.failure.class}`,
          `- message: ${result.failure.message}`,
          ...(result.failure.hint ? [`- hint: ${result.failure.hint}`] : []),
        ]
      : []),
  ].join('\n');
}

export function createCodexBridgeTask(
  run: MissionRun,
  options: Partial<Omit<CodexBridgeTask, 'id' | 'runId' | 'prompt' | 'status'>> & {
    prompt?: string;
    status?: CodexBridgeTaskStatus;
  } = {},
): CodexBridgeTask {
  const permissionStage = options.permissionStage ?? 'read_only';
  const sandbox = options.sandbox ?? (permissionStage === 'workspace_write' ? 'workspace-write' : 'read-only');

  return {
    id: `codex-bridge-${compactId(run.title)}-${run.id}`,
    runId: run.id,
    targetHost: options.targetHost ?? CODEX_BRIDGE_DEFAULT_HOST,
    codexBinary: options.codexBinary ?? CODEX_BRIDGE_DEFAULT_BINARY,
    workdir: options.workdir ?? CODEX_BRIDGE_DEFAULT_WORKDIR,
    permissionStage,
    sandbox,
    prompt: options.prompt ?? run.title,
    status: options.status ?? 'queued',
    jsonOut: options.jsonOut,
  };
}

export function createCodexRemoteSmokeCommand(task: Pick<CodexBridgeTask, 'targetHost' | 'codexBinary' | 'workdir' | 'jsonOut'>) {
  return [
    'python3 scripts/codex_remote_smoke.py',
    `--host ${task.targetHost}`,
    `--codex ${task.codexBinary}`,
    `--workdir ${task.workdir}`,
    ...(task.jsonOut ? [`--json-out ${task.jsonOut}`] : []),
  ].join(' ');
}

export function createCodexBridgeTaskArtifact(task: CodexBridgeTask): MissionArtifact {
  return {
    label: 'Codex Bridge Task',
    kind: 'codex-bridge-task',
    value: [
      `Task: ${task.id}`,
      `Run: ${task.runId}`,
      `Host: ${task.targetHost}`,
      `Binary: ${task.codexBinary}`,
      `Workdir: ${task.workdir}`,
      `Permission: ${task.permissionStage}`,
      `Sandbox: ${task.sandbox}`,
      `Status: ${task.status}`,
      '',
      'Smoke command:',
      createCodexRemoteSmokeCommand(task),
      '',
      'Prompt:',
      task.prompt,
    ].join('\n'),
    metadata: {
      taskId: task.id,
      runId: task.runId,
      targetHost: task.targetHost,
      codexBinary: task.codexBinary,
      permissionStage: task.permissionStage,
      sandbox: task.sandbox,
      status: task.status,
    },
  };
}

export function createCodexBridgeSmokeResultArtifact(result: CodexRemoteSmokeResult): MissionArtifact {
  return {
    label: 'Codex Bridge Smoke Result',
    kind: 'codex-bridge-result',
    value: smokeSummary(result),
    metadata: {
      status: result.status,
      targetHost: result.target.host,
      codexBinary: result.target.codex,
      healthOnly: result.target.healthOnly,
      failureClass: result.failure?.class ?? null,
    },
  };
}

export function attachCodexBridgeSmokeResult(
  run: MissionRun,
  result: CodexRemoteSmokeResult,
): MissionRun {
  const now = new Date().toISOString();
  const artifact = createCodexBridgeSmokeResultArtifact(result);
  const passed = result.status === 'pass';

  return {
    ...run,
    artifacts: [...run.artifacts, artifact],
    traceItems: [
      ...run.traceItems,
      {
        id: `${run.id}_codex_bridge_${Date.now().toString(36)}`,
        timestamp: now,
        agentId: 'devops',
        title: passed ? 'Codex bridge smoke passed' : 'Codex bridge smoke failed',
        summary: passed
          ? `${result.target.host} can run Codex and return artifacts.`
          : `${result.target.host} is blocked: ${result.failure?.class ?? 'unknown'}.`,
        tone: passed ? 'success' : 'danger',
      },
    ],
    updatedAt: now,
  };
}
