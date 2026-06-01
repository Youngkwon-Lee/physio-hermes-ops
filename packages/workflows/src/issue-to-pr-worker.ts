import { type AgentId, type MissionArtifact, type MissionRun } from '../../runtime/src/index';
import { getHarnessPermissionProfile } from '../../harness/src/index';

function getArtifact(run: MissionRun, kind: MissionArtifact['kind']) {
  return run.artifacts.find((artifact) => artifact.kind === kind);
}

function getPrimaryAgent(run: MissionRun): AgentId {
  const planArtifact = getArtifact(run, 'issue-to-pr-plan');
  const primaryAgent = planArtifact?.metadata?.primaryAgent;
  if (typeof primaryAgent === 'string') return primaryAgent as AgentId;

  return run.ownerAgents.find((agentId) => agentId !== 'planner' && agentId !== 'orchestrator')
    ?? run.ownerAgents[0]
    ?? 'orchestrator';
}

function getBranchName(run: MissionRun) {
  const prDraft = getArtifact(run, 'pr-draft');
  const branchName = prDraft?.metadata?.branchName;
  if (typeof branchName === 'string') return branchName;

  const branchPlan = getArtifact(run, 'branch-plan');
  const branchFromPlan = branchPlan?.value.match(/git switch -c ([^\s]+)/)?.[1];
  return branchFromPlan ?? `codex/agent-os-${run.id}`;
}

function getCheckCommands(run: MissionRun) {
  const checkPlan = getArtifact(run, 'check-plan');
  if (!checkPlan) return ['pnpm run typecheck'];

  return checkPlan.value
    .split('\n')
    .map((line) => line.replace(/^-\s*/, '').trim())
    .filter(Boolean);
}

function getDraftPrTitle(run: MissionRun) {
  const prDraft = getArtifact(run, 'pr-draft');
  const title = prDraft?.metadata?.title;
  return typeof title === 'string' ? title : `[Agent OS] ${run.title}`;
}

function getDraftPrBody(run: MissionRun) {
  const prDraft = getArtifact(run, 'pr-draft');
  return prDraft?.value ?? `Implements Mission Control run ${run.id}.`;
}

export function createIssueToPrWorkerArtifacts(
  run: MissionRun,
  options: { executeWorker?: boolean } = {},
): MissionArtifact[] {
  const primaryAgent = getPrimaryAgent(run);
  const permissionProfile = getHarnessPermissionProfile(primaryAgent);
  const branchName = getBranchName(run);
  const checkCommands = getCheckCommands(run);
  const executeWorker = options.executeWorker ?? false;

  return [
    {
      label: 'Worker Run',
      kind: 'worker-run',
      value: [
        `Mode: ${executeWorker ? 'execute' : 'dry-run'}`,
        `Worker: ${primaryAgent}`,
        `Branch: ${branchName}`,
        '',
        'Command plan:',
        `- git switch -c ${branchName}`,
        '- load docs/CANONICAL_DOCS.md',
        '- load docs/AI_NATIVE_COMPANY_OS_2026-05-26.md',
        '- load selected issue body and acceptance criteria',
        `- run ${primaryAgent} harness inside writable path boundary`,
        '- write implementation summary, changed files, and risks',
      ].join('\n'),
      metadata: {
        dryRun: !executeWorker,
        branchName,
        primaryAgent,
      },
    },
    {
      label: 'Permission Audit',
      kind: 'permission-audit',
      value: [
        `Agent: ${primaryAgent}`,
        '',
        'Writable:',
        ...permissionProfile.writable.map((item) => `- ${item}`),
        '',
        'Approval required:',
        ...permissionProfile.approvalRequired.map((item) => `- ${item}`),
        '',
        'Forbidden:',
        ...permissionProfile.forbidden.map((item) => `- ${item}`),
        '',
        'Stop conditions:',
        ...permissionProfile.stopConditions.map((item) => `- ${item}`),
      ].join('\n'),
      metadata: {
        primaryAgent,
        permissionProfile: primaryAgent,
      },
    },
    {
      label: 'Check Result',
      kind: 'check-result',
      value: [
        `Mode: ${executeWorker ? 'execute' : 'dry-run'}`,
        'Planned checks:',
        ...checkCommands.map((command) => `- ${command}`),
        '',
        executeWorker
          ? 'Worker execution is enabled; command output must be attached by the runtime adapter.'
          : 'Dry-run only. No repository files were changed and no checks were executed by Mission Control.',
      ].join('\n'),
      metadata: {
        dryRun: !executeWorker,
        checks: checkCommands.join(' | '),
      },
    },
    {
      label: 'Pull Request Payload',
      kind: 'pull-request',
      value: getDraftPrBody(run),
      metadata: {
        dryRun: true,
        title: getDraftPrTitle(run),
        branchName,
        baseBranch: 'main',
        pullRequestUrl: null,
      },
    },
  ];
}

export function attachIssueToPrWorkerArtifacts(
  run: MissionRun,
  options: { executeWorker?: boolean } = {},
): MissionRun {
  if (run.artifacts.some((artifact) => artifact.kind === 'worker-run')) return run;

  const now = new Date().toISOString();
  const artifacts = createIssueToPrWorkerArtifacts(run, options);

  return {
    ...run,
    artifacts: [...run.artifacts, ...artifacts],
    traceItems: [
      ...run.traceItems,
      {
        id: `${run.id}_worker_adapter_${Date.now().toString(36)}`,
        timestamp: now,
        agentId: 'orchestrator',
        title: 'Worker adapter prepared',
        summary: 'Dry-run worker command plan, permission audit, check result, and PR payload are attached.',
        tone: 'success',
      },
    ],
    updatedAt: now,
  };
}
