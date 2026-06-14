import type { MissionRun } from '../../runtime/src/index';

export interface DailyOpsSignals {
  checkedAt: string;
  milestone: {
    openRuns: number;
    blockedRuns: number;
    pendingApprovals: number;
    staleRuns: number;
  };
  productUsage: {
    encounters7d: number;
    encounters30d: number;
    completedEncounters30d: number;
    bookings7d: number;
    clientInvites30d: number;
  };
  funnel: {
    enabledAutomationRules: number;
    sentNotifications7d: number;
    failedNotifications7d: number;
    pendingReminders: number;
  };
  operations: {
    integrationsReady: number;
    integrationsDryRun: number;
    integrationsBlocked: number;
  };
}

function formatSignalLine(label: string, value: number) {
  return `- ${label}: ${value}`;
}

function createDefaultOpsBriefValue() {
  return [
    '# 오늘 점검',
    '',
    '## 목표',
    '운영 요약 · 개선 후보',
    '',
    '## 점검',
    '- 마일스톤',
    '- 사용',
    '- 유지보수',
    '- 퍼널',
    '- 모델',
    '- 배포',
    '',
    '## 결과',
    '- 보고서',
    '- 리스크',
    '- 개선',
    '- 승인',
  ].join('\n');
}

function createSignalOpsBriefValue(signals: DailyOpsSignals) {
  const risks = [
    signals.milestone.staleRuns > 0
      ? `지연 작업 ${signals.milestone.staleRuns}개`
      : null,
    signals.operations.integrationsBlocked > 0
      ? `막힌 연동 ${signals.operations.integrationsBlocked}개`
      : null,
    signals.funnel.failedNotifications7d > 0
      ? `알림 실패 ${signals.funnel.failedNotifications7d}개`
      : null,
    signals.productUsage.encounters7d === 0
      ? '최근 7일 방문 0개'
      : null,
  ].filter(Boolean);

  return [
    '# 오늘 점검',
    '',
    `시간: ${signals.checkedAt}`,
    '',
    '## 마일스톤',
    formatSignalLine('열림', signals.milestone.openRuns),
    formatSignalLine('승인', signals.milestone.pendingApprovals),
    formatSignalLine('막힘', signals.milestone.blockedRuns),
    formatSignalLine('지연', signals.milestone.staleRuns),
    '',
    '## 사용',
    formatSignalLine('방문 7일', signals.productUsage.encounters7d),
    formatSignalLine('방문 30일', signals.productUsage.encounters30d),
    formatSignalLine('완료 30일', signals.productUsage.completedEncounters30d),
    formatSignalLine('예약 7일', signals.productUsage.bookings7d),
    formatSignalLine('초대 30일', signals.productUsage.clientInvites30d),
    '',
    '## 퍼널',
    formatSignalLine('자동화', signals.funnel.enabledAutomationRules),
    formatSignalLine('알림 7일', signals.funnel.sentNotifications7d),
    formatSignalLine('실패 7일', signals.funnel.failedNotifications7d),
    formatSignalLine('리마인더', signals.funnel.pendingReminders),
    '',
    '## 연동',
    formatSignalLine('준비', signals.operations.integrationsReady),
    formatSignalLine('초안', signals.operations.integrationsDryRun),
    formatSignalLine('막힘', signals.operations.integrationsBlocked),
    '',
    '## 다음',
    risks.length > 0
      ? risks.map((risk) => `- ${risk}`).join('\n')
      : '- 리스크 없음',
    '- 계획 승인',
  ].join('\n');
}

export function createDailyOpsMissionRunDraft(signals?: DailyOpsSignals): MissionRun {
  const now = new Date().toISOString();
  const id = `daily-ops_${Date.now().toString(36)}`;
  const signalTone = signals?.operations.integrationsBlocked || signals?.funnel.failedNotifications7d
    ? 'warning' as const
    : 'success' as const;

  return {
    id,
    title: '오늘 운영 점검',
    description: [
      '마일스톤, 사용, 유지보수, 퍼널, 모델, 배포 점검.',
      '보고서, 개선, 승인.',
    ].join(' '),
    laneId: 'ops-finance',
    status: 'waiting-for-approval',
    priority: 'high',
    workflowIds: ['daily-ops', 'prd-to-issue', 'self-improvement'],
    ownerAgents: ['orchestrator', 'planner', 'qa', 'devops', 'backend', 'frontend', 'db'],
    approvalItems: [
      {
        id: `${id}_plan`,
        gate: 'plan',
        label: '오늘 계획 승인',
        status: 'pending',
        requiredBy: 'orchestrator',
      },
      {
        id: `${id}_issue`,
        gate: 'issue',
        label: '개선 이슈 생성',
        status: 'waived',
        requiredBy: 'planner',
      },
      {
        id: `${id}_pull_request`,
        gate: 'pull-request',
        label: '수정 PR 승인',
        status: 'waived',
        requiredBy: 'qa',
      },
    ],
    traceItems: [
      {
        id: `${id}_started`,
        timestamp: now,
        agentId: 'orchestrator',
        title: '운영 점검 시작',
        summary: '마일스톤, 사용, 유지보수, 퍼널, 모델, 배포.',
        tone: 'neutral',
      },
      {
        id: `${id}_plan_gate`,
        timestamp: now,
        agentId: 'planner',
        title: '계획 승인 대기',
        summary: '보고서 먼저, 개선은 승인 후.',
        tone: 'warning',
      },
      ...(signals ? [
        {
          id: `${id}_milestone_scan`,
          timestamp: now,
          agentId: 'orchestrator' as const,
          title: '마일스톤 점검',
          summary: `열림 ${signals.milestone.openRuns}, 승인 ${signals.milestone.pendingApprovals}, 지연 ${signals.milestone.staleRuns}.`,
          tone: signals.milestone.staleRuns > 0 ? 'warning' as const : 'success' as const,
        },
        {
          id: `${id}_usage_scan`,
          timestamp: now,
          agentId: 'planner' as const,
          title: '사용/퍼널 점검',
          summary: `방문 ${signals.productUsage.encounters7d}, 알림 ${signals.funnel.sentNotifications7d}, 실패 ${signals.funnel.failedNotifications7d}.`,
          tone: signals.funnel.failedNotifications7d > 0 ? 'warning' as const : 'success' as const,
        },
        {
          id: `${id}_ops_scan`,
          timestamp: now,
          agentId: 'devops' as const,
          title: '연동 점검',
          summary: `준비 ${signals.operations.integrationsReady}, 초안 ${signals.operations.integrationsDryRun}, 막힘 ${signals.operations.integrationsBlocked}.`,
          tone: signalTone,
        },
      ] : []),
    ],
    artifacts: [
      {
        label: '운영',
        kind: 'ops-brief',
        value: signals ? createSignalOpsBriefValue(signals) : createDefaultOpsBriefValue(),
        metadata: {
          workflow: 'daily-ops',
          cadence: signals ? 'manual-live-read' : 'manual-now-cron-later',
        },
      },
      {
        label: '규칙',
        kind: 'ops-brief',
        value: [
          '승인 범위 안에서만 자동 진행.',
          '',
          '- 읽기/보고: 가능',
          '- 이슈/PR 초안: 승인 후',
          '- 배포/고객/결제/인증/DB: 승인 필요',
        ].join('\n'),
        metadata: {
          approvalBoundary: 'human-click-required',
        },
      },
    ],
    createdAt: now,
    updatedAt: now,
  };
}
