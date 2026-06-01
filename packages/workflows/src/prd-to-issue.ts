import type { AgentId, MissionArtifact, MissionRun } from '../../runtime/src/index';
import { getCompanyLane } from '../../runtime/src/index';

export type IssueDraftKind =
  | 'prd'
  | 'frontend'
  | 'backend'
  | 'db'
  | 'qa'
  | 'devops'
  | 'growth'
  | 'mlops'
  | 'maintenance'
  | 'ops';

export interface IssueDraft {
  title: string;
  body: string;
  labels: string[];
  ownerAgent: AgentId;
  kind: IssueDraftKind;
}

const COMMON_ACCEPTANCE_CRITERIA = [
  '작업 범위와 제외 범위가 issue 본문에 명시되어 있다.',
  '필요한 approval gate가 Mission Control에 남아 있다.',
  '검증 결과는 green level과 명령어 기준으로 기록한다.',
];

function formatIssueBody(params: {
  run: MissionRun;
  problem: string;
  scope: string[];
  acceptanceCriteria: string[];
  risks: string[];
}) {
  const scope = params.scope.map((item) => `- ${item}`).join('\n');
  const acceptanceCriteria = params.acceptanceCriteria.map((item) => `- [ ] ${item}`).join('\n');
  const risks = params.risks.map((item) => `- ${item}`).join('\n');

  return [
    '## Mission',
    params.run.title,
    '',
    '## Problem',
    params.problem,
    '',
    '## Scope',
    scope,
    '',
    '## Acceptance Criteria',
    acceptanceCriteria,
    '',
    '## Risk Notes',
    risks,
    '',
    '## Harness',
    `- Lane: ${params.run.laneId}`,
    `- Priority: ${params.run.priority}`,
    `- Source run: ${params.run.id}`,
  ].join('\n');
}

function createPrdArtifact(run: MissionRun): MissionArtifact {
  const lane = getCompanyLane(run.laneId);

  return {
    label: 'PRD Draft',
    kind: 'prd',
    value: [
      `# ${run.title}`,
      '',
      '## Goal',
      run.description,
      '',
      '## Operating Lane',
      `${lane?.label ?? run.laneId} / ${lane?.name ?? run.laneId}`,
      '',
      '## Primary Agents',
      run.ownerAgents.join(', '),
      '',
      '## Default Green Level',
      lane?.defaultGreenLevel ?? 'targeted',
      '',
      '## Approval Gates',
      run.approvalItems.map((item) => `- ${item.label}: ${item.status}`).join('\n'),
    ].join('\n'),
    metadata: {
      laneId: run.laneId,
      workflow: 'prd-to-issue',
    },
  };
}

function featureIssues(run: MissionRun): IssueDraft[] {
  return [
    {
      title: `[Planner] PRD and task split: ${run.title}`,
      kind: 'prd',
      ownerAgent: 'planner',
      labels: ['agent-os', 'planner', `lane:${run.laneId}`],
      body: formatIssueBody({
        run,
        problem: '사용자 목표를 구현 가능한 PRD, 작업 분리, acceptance criteria로 고정한다.',
        scope: [
          'PRD 초안 작성',
          'frontend/backend/DB/QA/DevOps 작업 분리',
          '명시적인 out-of-scope와 human gate 정의',
        ],
        acceptanceCriteria: [
          ...COMMON_ACCEPTANCE_CRITERIA,
          '각 하위 issue가 한 PR로 닫힐 수 있는 크기다.',
        ],
        risks: ['기획이 넓어지면 Issue To PR 하네스가 과도하게 큰 diff를 만들 수 있다.'],
      }),
    },
    {
      title: `[Frontend] UI workflow: ${run.title}`,
      kind: 'frontend',
      ownerAgent: 'frontend',
      labels: ['agent-os', 'frontend', `lane:${run.laneId}`],
      body: formatIssueBody({
        run,
        problem: '사용자가 기능을 볼 수 있는 화면, 상태, 승인 UX를 구현한다.',
        scope: [
          '기존 디자인 시스템에 맞는 페이지/컴포넌트 변경',
          'loading/empty/error state',
          'desktop/mobile visual smoke',
        ],
        acceptanceCriteria: [
          ...COMMON_ACCEPTANCE_CRITERIA,
          '변경 화면이 Playwright smoke에서 console/page error 없이 렌더링된다.',
        ],
        risks: ['UI 변경이 clinical/dashboard 흐름과 겹치면 regression smoke가 필요하다.'],
      }),
    },
    {
      title: `[Backend] Server flow: ${run.title}`,
      kind: 'backend',
      ownerAgent: 'backend',
      labels: ['agent-os', 'backend', `lane:${run.laneId}`],
      body: formatIssueBody({
        run,
        problem: '제품 동작을 server action, domain service, repository 경계에 맞춰 구현한다.',
        scope: [
          'bounded context 선택',
          'server action/domain service/repository 분리',
          '권한과 validation error path 정의',
        ],
        acceptanceCriteria: [
          ...COMMON_ACCEPTANCE_CRITERIA,
          'repository를 route/page에서 직접 호출하지 않는다.',
        ],
        risks: ['auth, billing, DB schema 변경이 필요하면 별도 gate로 분리한다.'],
      }),
    },
    {
      title: `[QA] Test and release checks: ${run.title}`,
      kind: 'qa',
      ownerAgent: 'qa',
      labels: ['agent-os', 'qa', `lane:${run.laneId}`],
      body: formatIssueBody({
        run,
        problem: '기능 변경의 회귀 위험과 green level을 검증한다.',
        scope: [
          'targeted unit/integration test 선정',
          'typecheck/lint 결과 기록',
          'preview smoke checklist 작성',
        ],
        acceptanceCriteria: [
          ...COMMON_ACCEPTANCE_CRITERIA,
          'PR 본문에 통과/미통과/waived checks가 명확히 기록된다.',
        ],
        risks: ['기존 failing test가 있으면 원인과 범위를 별도 maintenance issue로 분리한다.'],
      }),
    },
  ];
}

function laneSpecificIssues(run: MissionRun): IssueDraft[] {
  if (run.laneId === 'feature') return featureIssues(run);

  const lane = getCompanyLane(run.laneId);
  const owner = run.ownerAgents[0] ?? 'orchestrator';
  const kindByLane: Record<string, IssueDraftKind> = {
    maintenance: 'maintenance',
    devops: 'devops',
    mlops: 'mlops',
    growth: 'growth',
    'db-data': 'db',
    'ops-finance': 'ops',
  };

  return [
    {
      title: `[${lane?.label ?? run.laneId}] ${run.title}`,
      kind: kindByLane[run.laneId] ?? 'ops',
      ownerAgent: owner,
      labels: ['agent-os', `lane:${run.laneId}`, `owner:${owner}`],
      body: formatIssueBody({
        run,
        problem: run.description,
        scope: lane?.outputs ?? ['mission output', 'approval note', 'verification record'],
        acceptanceCriteria: [
          ...COMMON_ACCEPTANCE_CRITERIA,
          `${lane?.defaultGreenLevel ?? 'targeted'} green level 기준을 만족하거나 waiver를 기록한다.`,
        ],
        risks: lane?.guardrails ?? ['human approval boundary must remain explicit'],
      }),
    },
  ];
}

export function createPrdToIssueDrafts(run: MissionRun): IssueDraft[] {
  return laneSpecificIssues(run);
}

export function createPrdToIssueArtifacts(run: MissionRun): MissionArtifact[] {
  const issueDrafts = createPrdToIssueDrafts(run);

  return [
    createPrdArtifact(run),
    ...issueDrafts.map((issue, index) => ({
      label: `Issue Draft ${index + 1}: ${issue.title}`,
      value: issue.body,
      kind: 'issue-draft' as const,
      metadata: {
        title: issue.title,
        labels: issue.labels.join(','),
        ownerAgent: issue.ownerAgent,
        issueKind: issue.kind,
      },
    })),
  ];
}

export function attachPrdToIssueArtifacts(run: MissionRun): MissionRun {
  if (!run.workflowIds.includes('prd-to-issue')) return run;
  if (run.artifacts.some((artifact) => artifact.kind === 'issue-draft')) return run;

  const now = new Date().toISOString();
  const artifacts = createPrdToIssueArtifacts(run);

  return {
    ...run,
    artifacts: [...run.artifacts, ...artifacts],
    traceItems: [
      ...run.traceItems,
      {
        id: `${run.id}_issue_drafts_created_${Date.now().toString(36)}`,
        timestamp: now,
        agentId: 'planner',
        title: 'Issue drafts created',
        summary: `${artifacts.filter((artifact) => artifact.kind === 'issue-draft').length} GitHub issue drafts are ready for the Create issues gate.`,
        tone: 'success',
      },
    ],
    updatedAt: now,
  };
}

export function attachSimulatedGitHubIssueArtifacts(run: MissionRun): MissionRun {
  if (run.artifacts.some((artifact) => artifact.kind === 'github-issue')) return run;

  const issueDrafts = run.artifacts.filter((artifact) => artifact.kind === 'issue-draft');
  if (issueDrafts.length === 0) return run;

  const now = new Date().toISOString();

  return {
    ...run,
    artifacts: [
      ...run.artifacts,
      ...issueDrafts.map((artifact, index) => ({
        label: `GitHub Issue Payload ${index + 1}`,
        value: String(artifact.metadata?.title ?? artifact.label),
        kind: 'github-issue' as const,
        metadata: {
          title: String(artifact.metadata?.title ?? artifact.label),
          labels: String(artifact.metadata?.labels ?? ''),
          ownerAgent: String(artifact.metadata?.ownerAgent ?? 'planner'),
          issueNumber: null,
          issueUrl: null,
          dryRun: true,
        },
      })),
    ],
    traceItems: [
      ...run.traceItems,
      {
        id: `${run.id}_github_issue_payloads_${Date.now().toString(36)}`,
        timestamp: now,
        agentId: 'planner',
        title: 'GitHub issue payloads prepared',
        summary: `${issueDrafts.length} issue payloads are ready for the GitHub adapter.`,
        tone: 'success',
      },
    ],
    updatedAt: now,
  };
}
