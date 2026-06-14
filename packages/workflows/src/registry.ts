import type { AgentId, ApprovalGate, WorkflowId } from '../../runtime/src/index';

export type WorkflowState = 'draft' | 'ready' | 'active' | 'paused' | 'completed';

export interface WorkflowStep {
  id: string;
  label: string;
  owner: AgentId;
  output: string;
  approvalGate?: ApprovalGate;
}

export interface AgentWorkflow {
  id: WorkflowId;
  name: string;
  state: WorkflowState;
  trigger: string;
  goal: string;
  steps: WorkflowStep[];
}

export const AGENT_WORKFLOWS: AgentWorkflow[] = [
  {
    id: 'daily-ops',
    name: 'Daily Operating Loop',
    state: 'ready',
    trigger: '운영자가 Run Daily Ops를 누르거나 승인된 cron/heartbeat가 stale work를 감지한다.',
    goal: '마일스톤 진행, 고객/전문가 사용성, 유지보수, 퍼널, MLOps, DevOps 리스크를 하나의 운영 브리프로 모은다.',
    steps: [
      { id: 'milestone-scan', label: '마일스톤과 막힌 gate 확인', owner: 'orchestrator', output: 'milestone status' },
      { id: 'usage-funnel', label: '고객/전문가 사용 흐름과 이탈 지점 점검', owner: 'planner', output: 'funnel brief' },
      { id: 'maintenance-scan', label: '버그, 회귀, 느린 화면, 실패 trace 분류', owner: 'qa', output: 'maintenance queue' },
      { id: 'ops-health', label: '배포, cron, 비용, 장애 리스크 점검', owner: 'devops', output: 'ops health brief' },
      { id: 'improvement-plan', label: '개선 issue와 PR 후보 생성', owner: 'orchestrator', output: 'next action plan', approvalGate: 'plan' },
    ],
  },
  {
    id: 'prd-to-issue',
    name: 'PRD To Issue Harness',
    state: 'ready',
    trigger: '사용자가 기능 목표를 입력한다.',
    goal: '기능 목표를 PRD, acceptance criteria, owner agent, GitHub issue로 분해한다.',
    steps: [
      { id: 'capture-goal', label: '목표와 제약 수집', owner: 'planner', output: 'mission brief' },
      { id: 'risk-split', label: '위험도와 작업 분리', owner: 'orchestrator', output: 'agent task split' },
      { id: 'write-prd', label: 'PRD와 acceptance criteria 작성', owner: 'planner', output: 'PRD draft', approvalGate: 'plan' },
      { id: 'create-issues', label: 'GitHub issue 생성', owner: 'planner', output: 'linked issues', approvalGate: 'issue' },
    ],
  },
  {
    id: 'issue-to-pr',
    name: 'Issue To PR Harness',
    state: 'draft',
    trigger: '승인된 GitHub issue가 구현 대기 상태가 된다.',
    goal: '격리된 branch에서 구현, 검증, draft PR 생성을 완료한다.',
    steps: [
      { id: 'repo-context', label: '관련 파일과 canonical docs 탐색', owner: 'orchestrator', output: 'context pack' },
      { id: 'implement', label: '권한 boundary 안에서 구현', owner: 'backend', output: 'code changes' },
      { id: 'review', label: '테스트와 회귀 리뷰', owner: 'qa', output: 'review findings' },
      { id: 'open-pr', label: 'Draft PR 생성', owner: 'devops', output: 'draft PR', approvalGate: 'pull-request' },
    ],
  },
  {
    id: 'pr-to-deploy',
    name: 'PR To Deploy Harness',
    state: 'draft',
    trigger: 'PR이 승인되고 CI가 통과한다.',
    goal: 'preview smoke, release note, rollback plan을 만든 뒤 승인된 배포만 실행한다.',
    steps: [
      { id: 'preview', label: 'Preview deployment 확인', owner: 'devops', output: 'preview URL', approvalGate: 'preview' },
      { id: 'smoke', label: '핵심 경로 smoke test', owner: 'qa', output: 'smoke report' },
      { id: 'release-plan', label: '릴리즈와 rollback 계획 작성', owner: 'devops', output: 'release plan' },
      { id: 'production', label: 'Production deploy', owner: 'devops', output: 'deploy event', approvalGate: 'production' },
    ],
  },
  {
    id: 'self-improvement',
    name: 'Ralph/Ouroboros Improvement Harness',
    state: 'draft',
    trigger: '반복 실패 trace나 review 패턴이 감지된다.',
    goal: '실패 패턴을 eval, checklist, permission rule 개선 PR로 바꾼다.',
    steps: [
      { id: 'cluster-failures', label: '실패 trace 클러스터링', owner: 'qa', output: 'failure pattern' },
      { id: 'propose-rule', label: 'harness 개선안 작성', owner: 'orchestrator', output: 'rule proposal' },
      { id: 'shadow-test', label: 'shadow eval 실행', owner: 'qa', output: 'eval result' },
      { id: 'harness-pr', label: 'Harness 개선 PR 생성', owner: 'devops', output: 'draft PR', approvalGate: 'pull-request' },
    ],
  },
];

export function getAgentWorkflow(workflowId: WorkflowId) {
  return AGENT_WORKFLOWS.find((workflow) => workflow.id === workflowId);
}
