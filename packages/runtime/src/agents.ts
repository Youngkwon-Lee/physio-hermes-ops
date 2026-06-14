export type AgentId =
  | 'orchestrator'
  | 'planner'
  | 'frontend'
  | 'backend'
  | 'db'
  | 'qa'
  | 'devops';

export type ApprovalGate =
  | 'plan'
  | 'issue'
  | 'pull-request'
  | 'migration'
  | 'preview'
  | 'production';

export interface AgentProfile {
  id: AgentId;
  name: string;
  label: string;
  role: string;
  defaultInputs: string[];
  defaultOutputs: string[];
  approvalGates: ApprovalGate[];
}

export const AGENT_PROFILES: AgentProfile[] = [
  {
    id: 'orchestrator',
    name: 'Orchestrator',
    label: '작업 지휘',
    role: '전체 작업을 분해하고 우선순위, owner, 승인 경계를 결정한다.',
    defaultInputs: ['mission', 'repo state', 'open issues', 'approval policy'],
    defaultOutputs: ['run plan', 'agent assignment', 'approval request'],
    approvalGates: ['plan', 'pull-request', 'production'],
  },
  {
    id: 'planner',
    name: 'PM/Planner Agent',
    label: '기획',
    role: '자연어 목표를 PRD, user story, acceptance criteria, issue로 바꾼다.',
    defaultInputs: ['goal', 'strategy docs', 'customer evidence', 'screenshots'],
    defaultOutputs: ['PRD', 'task split', 'GitHub issues'],
    approvalGates: ['plan', 'issue'],
  },
  {
    id: 'frontend',
    name: 'Frontend Agent',
    label: '프론트엔드',
    role: 'UI 컴포넌트, 페이지, 상태관리, 브라우저 검증을 담당한다.',
    defaultInputs: ['issue', 'design constraints', 'existing components'],
    defaultOutputs: ['UI changes', 'visual check', 'frontend test notes'],
    approvalGates: ['pull-request', 'preview'],
  },
  {
    id: 'backend',
    name: 'Backend Agent',
    label: '백엔드',
    role: 'server action, API, domain service, repository flow를 담당한다.',
    defaultInputs: ['issue', 'architecture docs', 'schemas'],
    defaultOutputs: ['server changes', 'domain tests', 'risk note'],
    approvalGates: ['pull-request'],
  },
  {
    id: 'db',
    name: 'DB Agent',
    label: '데이터베이스',
    role: 'schema, migration, RLS, 데이터 품질과 DB 문서 동기화를 담당한다.',
    defaultInputs: ['data requirement', 'current schema docs', 'migration rules'],
    defaultOutputs: ['migration plan', 'RLS review', 'DB docs update'],
    approvalGates: ['migration', 'pull-request'],
  },
  {
    id: 'qa',
    name: 'QA/Review Agent',
    label: '품질',
    role: '테스트, 회귀검사, 버그 탐지, PR 리뷰를 담당한다.',
    defaultInputs: ['PR diff', 'acceptance criteria', 'test history'],
    defaultOutputs: ['review findings', 'test checklist', 'release risk'],
    approvalGates: ['pull-request', 'preview'],
  },
  {
    id: 'devops',
    name: 'DevOps Agent',
    label: '배포',
    role: 'CI/CD, preview, production deploy, monitoring, rollback을 담당한다.',
    defaultInputs: ['approved PR', 'CI status', 'preview deployment'],
    defaultOutputs: ['deploy plan', 'smoke report', 'rollback note'],
    approvalGates: ['preview', 'production'],
  },
];

export function getAgentProfile(agentId: AgentId) {
  return AGENT_PROFILES.find((agent) => agent.id === agentId);
}
