import type { MissionArtifact, MissionRun } from '../../runtime/src/index';

function envValue(key: string) {
  const processLike = globalThis as typeof globalThis & {
    process?: {
      env?: Record<string, string | undefined>;
    };
  };

  return processLike.process?.env?.[key];
}

function getArtifact(run: MissionRun, kind: MissionArtifact['kind']) {
  return run.artifacts.find((artifact) => artifact.kind === kind);
}

function getBranchName(run: MissionRun) {
  const pullRequest = getArtifact(run, 'pull-request');
  const branchName = pullRequest?.metadata?.branchName;
  if (typeof branchName === 'string') return branchName;

  const prDraft = getArtifact(run, 'pr-draft');
  const draftBranchName = prDraft?.metadata?.branchName;
  return typeof draftBranchName === 'string' ? draftBranchName : `codex/agent-os-${run.id}`;
}

function getPreviewUrl(run: MissionRun) {
  const existingPreview = getArtifact(run, 'preview-deploy');
  const previewUrl = existingPreview?.metadata?.previewUrl;
  if (typeof previewUrl === 'string' && previewUrl.length > 0) return previewUrl;

  const branchName = getBranchName(run).replace(/[^a-zA-Z0-9-]/g, '-').toLowerCase();
  return `https://${branchName}.vercel.app`;
}

function shouldDeployPreview() {
  return envValue('AGENT_OS_VERCEL_PREVIEW_DEPLOY') === '1'
    || envValue('AGENT_OS_VERCEL_PREVIEW_DEPLOY') === 'true';
}

function shouldPromoteProduction() {
  return envValue('AGENT_OS_VERCEL_PRODUCTION_PROMOTE') === '1'
    || envValue('AGENT_OS_VERCEL_PRODUCTION_PROMOTE') === 'true';
}

export function createPrToPreviewArtifacts(run: MissionRun): MissionArtifact[] {
  const executePreviewDeploy = shouldDeployPreview();
  const branchName = getBranchName(run);
  const previewUrl = getPreviewUrl(run);

  return [
    {
      label: 'Preview Deployment',
      kind: 'preview-deploy',
      value: [
        `Mode: ${executePreviewDeploy ? 'execute' : 'dry-run'}`,
        `Branch: ${branchName}`,
        `Preview URL: ${previewUrl}`,
        '',
        'Command plan:',
        executePreviewDeploy
          ? '- vercel deploy --prebuilt'
          : '- wait for Vercel Git integration preview or run vercel deploy',
        '- vercel inspect <preview-url>',
        '- attach deployment URL and build status to this run',
      ].join('\n'),
      metadata: {
        dryRun: !executePreviewDeploy,
        branchName,
        previewUrl,
      },
    },
    {
      label: 'Preview Smoke Report',
      kind: 'smoke-report',
      value: [
        `Mode: ${executePreviewDeploy ? 'execute' : 'dry-run'}`,
        'Smoke checklist:',
        '- preview URL responds with 2xx',
        '- changed route renders without console/page errors',
        '- auth-protected route redirects correctly when logged out',
        '- no obvious mobile/desktop layout overlap',
        '- core mutation path is not run against production data',
        '',
        executePreviewDeploy
          ? 'Runtime adapter must attach Playwright/browser output before production approval.'
          : 'Dry-run only. Smoke checklist is prepared but not executed against a live preview.',
      ].join('\n'),
      metadata: {
        dryRun: !executePreviewDeploy,
        previewUrl,
      },
    },
    {
      label: 'Rollback Plan',
      kind: 'rollback-plan',
      value: [
        'Rollback command plan:',
        '- vercel rollback',
        '- or vercel rollback <deployment-url-or-id>',
        '',
        'Rollback trigger:',
        '- smoke failure after promote',
        '- auth/session regression',
        '- database/RLS regression',
        '- elevated runtime errors in first 30 minutes',
      ].join('\n'),
      metadata: {
        previewUrl,
      },
    },
    {
      label: 'Monitoring Plan',
      kind: 'monitoring-plan',
      value: [
        'First 30 minutes:',
        '- watch Vercel runtime logs',
        '- watch function error rate',
        '- check slow route/function duration changes',
        '- check user-facing smoke path once after promote',
        '',
        'Log command plan:',
        '- vercel logs <deployment-url>',
        '- vercel inspect <deployment-url>',
      ].join('\n'),
      metadata: {
        previewUrl,
      },
    },
  ];
}

export function createProductionDeployArtifacts(run: MissionRun): MissionArtifact[] {
  const promoteProduction = shouldPromoteProduction();
  const previewUrl = getPreviewUrl(run);

  return [
    {
      label: 'Production Deploy Payload',
      kind: 'production-deploy',
      value: [
        `Mode: ${promoteProduction ? 'execute' : 'dry-run'}`,
        `Validated preview: ${previewUrl}`,
        '',
        'Command plan:',
        promoteProduction
          ? `- vercel promote ${previewUrl}`
          : `- vercel promote ${previewUrl}`,
        '- verify production alias',
        '- start monitoring window',
        '',
        promoteProduction
          ? 'Production promote is enabled. Runtime adapter must attach deployment event output.'
          : 'Dry-run only. Production promote is not executed by Mission Control.',
      ].join('\n'),
      metadata: {
        dryRun: !promoteProduction,
        previewUrl,
        productionUrl: envValue('AGENT_OS_PRODUCTION_URL') ?? null,
      },
    },
    {
      label: 'Release Note',
      kind: 'release-note',
      value: [
        `Released mission: ${run.title}`,
        '',
        'Included artifacts:',
        ...run.artifacts
          .filter((artifact) => artifact.kind)
          .slice(-8)
          .map((artifact) => `- ${artifact.label}`),
        '',
        'Post-release owner:',
        '- DevOps Agent monitors runtime logs',
        '- QA Agent validates smoke path',
        '- Orchestrator opens rollback gate if monitoring fails',
      ].join('\n'),
      metadata: {
        previewUrl,
      },
    },
  ];
}

export function attachPrToPreviewArtifacts(run: MissionRun): MissionRun {
  if (run.artifacts.some((artifact) => artifact.kind === 'preview-deploy')) return run;

  const now = new Date().toISOString();
  const artifacts = createPrToPreviewArtifacts(run);

  return {
    ...run,
    artifacts: [...run.artifacts, ...artifacts],
    traceItems: [
      ...run.traceItems,
      {
        id: `${run.id}_preview_ready_${Date.now().toString(36)}`,
        timestamp: now,
        agentId: 'devops',
        title: 'Preview deploy package prepared',
        summary: 'Preview deployment, smoke report, rollback plan, and monitoring plan are attached.',
        tone: 'success',
      },
    ],
    updatedAt: now,
  };
}

export function attachProductionDeployArtifacts(run: MissionRun): MissionRun {
  if (run.artifacts.some((artifact) => artifact.kind === 'production-deploy')) return run;

  const now = new Date().toISOString();
  const artifacts = createProductionDeployArtifacts(run);

  return {
    ...run,
    artifacts: [...run.artifacts, ...artifacts],
    traceItems: [
      ...run.traceItems,
      {
        id: `${run.id}_production_payload_${Date.now().toString(36)}`,
        timestamp: now,
        agentId: 'devops',
        title: 'Production deploy payload prepared',
        summary: 'Production promote payload and release note are attached. Dry-run by default.',
        tone: 'success',
      },
    ],
    updatedAt: now,
  };
}
