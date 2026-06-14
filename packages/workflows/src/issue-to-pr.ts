import { getAgentProfile, type MissionArtifact, type MissionRun } from '../../runtime/src/index';
import { BASE_HARNESS_EVALS, getHarnessPermissionProfile } from '../../harness/src/index';

function slugify(value: string) {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9가-힣]+/g, '-')
    .replace(/^-|-$/g, '')
    .slice(0, 44) || 'mission';
}

function getIssueArtifacts(run: MissionRun) {
  const githubIssues = run.artifacts.filter((artifact) => artifact.kind === 'github-issue');
  if (githubIssues.length > 0) return githubIssues;
  return run.artifacts.filter((artifact) => artifact.kind === 'issue-draft');
}

function createTargetIssueList(run: MissionRun) {
  return getIssueArtifacts(run).map((artifact, index) => ({
    index: index + 1,
    title: String(artifact.metadata?.title ?? artifact.label),
    url: typeof artifact.metadata?.issueUrl === 'string' ? artifact.metadata.issueUrl : null,
    ownerAgent: String(artifact.metadata?.ownerAgent ?? 'orchestrator'),
  }));
}

function createCheckList(run: MissionRun) {
  const laneChecks = run.laneId === 'feature'
    ? ['pnpm run typecheck', 'pnpm exec eslint <changed-files>', 'Playwright preview smoke for changed route']
    : ['pnpm run typecheck', 'pnpm exec eslint <changed-files>'];
  const blockingChecks = BASE_HARNESS_EVALS
    .filter((evalItem) => evalItem.severity === 'blocking')
    .map((evalItem) => evalItem.command ?? evalItem.label);

  return Array.from(new Set([...laneChecks, ...blockingChecks]));
}

function createDraftPrBody(run: MissionRun, branchName: string) {
  const targetIssues = createTargetIssueList(run);
  const issueLines = targetIssues.map((issue) => (
    issue.url
      ? `- ${issue.title}: ${issue.url}`
      : `- ${issue.title}`
  ));
  const checks = createCheckList(run).map((check) => `- [ ] ${check}`);

  return [
    '## Summary',
    `Implements the approved Mission Control run: ${run.title}.`,
    '',
    '## Target Issues',
    issueLines.join('\n') || '- No linked issue yet.',
    '',
    '## Branch',
    branchName,
    '',
    '## Testing',
    checks.join('\n'),
    '',
    '## Risk Notes',
    '- Keep changes inside the selected owner agent permission boundary.',
    '- Record waived checks explicitly before requesting review.',
    '- Do not deploy production changes until preview and production gates are approved.',
  ].join('\n');
}

export function createIssueToPrArtifacts(run: MissionRun): MissionArtifact[] {
  const targetIssues = createTargetIssueList(run);
  const branchName = `codex/agent-os-${slugify(run.title)}`;
  const primaryAgentId = run.ownerAgents.find((agentId) => agentId !== 'planner' && agentId !== 'orchestrator')
    ?? run.ownerAgents[0]
    ?? 'orchestrator';
  const primaryAgent = getAgentProfile(primaryAgentId);
  const permissionProfile = getHarnessPermissionProfile(primaryAgentId);
  const checks = createCheckList(run);

  return [
    {
      label: 'Issue To PR Plan',
      kind: 'issue-to-pr-plan',
      value: [
        `Primary worker: ${primaryAgent?.name ?? primaryAgentId}`,
        `Target issues: ${targetIssues.length}`,
        `Branch: ${branchName}`,
        `Green level target: ${run.artifacts.find((artifact) => artifact.label === 'Target green level')?.value ?? 'merge-ready'}`,
        '',
        'Context pack:',
        '- docs/CANONICAL_DOCS.md',
        '- docs/AI_NATIVE_COMPANY_OS_2026-05-26.md',
        '- docs/ARCHITECTURE_RULES.md',
        '- docs/SYSTEM_ARCHITECTURE.md',
      ].join('\n'),
      metadata: {
        branchName,
        primaryAgent: primaryAgentId,
        targetIssueCount: targetIssues.length,
      },
    },
    {
      label: 'Branch Plan',
      kind: 'branch-plan',
      value: [
        `git switch -c ${branchName}`,
        '',
        'Worker start condition:',
        '- clean/understood worktree state',
        '- selected target issue',
        '- permission profile loaded',
        '',
        'Writable paths:',
        ...permissionProfile.writable.map((path) => `- ${path}`),
        '',
        'Approval required:',
        ...permissionProfile.approvalRequired.map((gate) => `- ${gate}`),
      ].join('\n'),
      metadata: {
        branchName,
        primaryAgent: primaryAgentId,
      },
    },
    {
      label: 'Check Plan',
      kind: 'check-plan',
      value: checks.map((check) => `- ${check}`).join('\n'),
      metadata: {
        checks: checks.join(' | '),
      },
    },
    {
      label: 'Draft PR Payload',
      kind: 'pr-draft',
      value: createDraftPrBody(run, branchName),
      metadata: {
        title: `[Agent OS] ${run.title}`,
        branchName,
        baseBranch: 'main',
        dryRun: true,
      },
    },
  ];
}

export function attachIssueToPrArtifacts(run: MissionRun): MissionRun {
  if (!run.workflowIds.includes('issue-to-pr')) return run;
  if (run.artifacts.some((artifact) => artifact.kind === 'pr-draft')) return run;

  const now = new Date().toISOString();
  const artifacts = createIssueToPrArtifacts(run);

  return {
    ...run,
    artifacts: [...run.artifacts, ...artifacts],
    traceItems: [
      ...run.traceItems,
      {
        id: `${run.id}_issue_to_pr_plan_${Date.now().toString(36)}`,
        timestamp: now,
        agentId: 'orchestrator',
        title: 'Issue To PR plan prepared',
        summary: 'Branch plan, check plan, and draft PR payload are ready for the worker adapter.',
        tone: 'success',
      },
    ],
    updatedAt: now,
  };
}
