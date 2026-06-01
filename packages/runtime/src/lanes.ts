import type { AgentId, ApprovalGate } from './agents';
import type { GreenLevel, WorkflowId } from './contracts';

export type CompanyLaneId =
  | 'feature'
  | 'maintenance'
  | 'devops'
  | 'mlops'
  | 'growth'
  | 'db-data'
  | 'ops-finance';

export interface CompanyLane {
  id: CompanyLaneId;
  name: string;
  label: string;
  objective: string;
  defaultWorkflowIds: WorkflowId[];
  primaryAgents: AgentId[];
  approvalGates: ApprovalGate[];
  defaultGreenLevel: GreenLevel;
  triggers: string[];
  outputs: string[];
  guardrails: string[];
}

export const COMPANY_LANES: CompanyLane[] = [
  {
    id: 'feature',
    name: 'Feature Lane',
    label: '기능개발',
    objective: '새 제품 기능을 PRD, issue, PR, preview, deploy approval로 이동시킨다.',
    defaultWorkflowIds: ['prd-to-issue', 'issue-to-pr', 'pr-to-deploy'],
    primaryAgents: ['planner', 'orchestrator', 'frontend', 'backend', 'db', 'qa', 'devops'],
    approvalGates: ['plan', 'issue', 'pull-request', 'preview', 'production'],
    defaultGreenLevel: 'release-ready',
    triggers: ['new feature request', 'customer evidence', 'roadmap priority'],
    outputs: ['PRD', 'GitHub issues', 'draft PR', 'preview report', 'release note'],
    guardrails: ['bounded context selected', 'schema risk classified', 'preview smoke required'],
  },
  {
    id: 'maintenance',
    name: 'Maintenance Lane',
    label: '유지보수',
    objective: '버그, 회귀, flaky test, 성능 저하, 기술부채를 작은 fix PR로 정리한다.',
    defaultWorkflowIds: ['issue-to-pr'],
    primaryAgents: ['orchestrator', 'qa', 'frontend', 'backend'],
    approvalGates: ['pull-request'],
    defaultGreenLevel: 'merge-ready',
    triggers: ['CI failure', 'bug report', 'slow route', 'dependency drift', 'flaky smoke'],
    outputs: ['failure classification', 'regression fix PR', 'test note', 'risk note'],
    guardrails: ['stale branch checked before blame', 'targeted failing test reproduced', 'no unrelated refactor'],
  },
  {
    id: 'devops',
    name: 'DevOps Lane',
    label: '배포/운영',
    objective: 'CI/CD, preview, production deploy, incident response, rollback을 승인 중심으로 운영한다.',
    defaultWorkflowIds: ['pr-to-deploy'],
    primaryAgents: ['devops', 'qa', 'orchestrator'],
    approvalGates: ['preview', 'production'],
    defaultGreenLevel: 'release-ready',
    triggers: ['approved PR', 'CI red', 'preview failure', 'incident alert', 'rollback request'],
    outputs: ['deploy plan', 'preview smoke report', 'incident timeline', 'rollback note'],
    guardrails: ['production locked until human approval', 'rollback path documented', 'first-30-minute monitoring plan'],
  },
  {
    id: 'mlops',
    name: 'MLOps Lane',
    label: '모델/평가',
    objective: 'LLM 품질, prompt, eval set, 비용, 실패 케이스를 개선 PR로 연결한다.',
    defaultWorkflowIds: ['self-improvement'],
    primaryAgents: ['qa', 'backend', 'orchestrator'],
    approvalGates: ['plan', 'pull-request'],
    defaultGreenLevel: 'merge-ready',
    triggers: ['eval regression', 'cost spike', 'hallucination report', 'prompt drift', 'RAG quality issue'],
    outputs: ['eval report', 'failure cluster', 'prompt/model policy PR', 'cost note'],
    guardrails: ['clinical final judgment never automated', 'shadow eval before prompt change', 'human approval for model policy'],
  },
  {
    id: 'growth',
    name: 'Growth Lane',
    label: '퍼널/성장',
    objective: '랜딩, 가입, 온보딩, 리텐션, 가격/패키지 실험을 issue와 PR로 만든다.',
    defaultWorkflowIds: ['daily-ops', 'prd-to-issue', 'issue-to-pr'],
    primaryAgents: ['planner', 'frontend', 'qa', 'orchestrator'],
    approvalGates: ['plan', 'issue', 'pull-request', 'preview'],
    defaultGreenLevel: 'workspace',
    triggers: ['signup drop-off', 'landing copy review', 'SEO opportunity', 'pricing experiment', 'retention gap'],
    outputs: ['experiment brief', 'copy/UI PR', 'funnel metric note', 'rollback plan'],
    guardrails: ['no medical promises', 'experiment metric defined', 'copy reviewed before publish'],
  },
  {
    id: 'db-data',
    name: 'DB/Data Lane',
    label: 'DB/데이터',
    objective: 'schema, RLS, 데이터 품질, ontology drift, DB 문서 동기화를 관리한다.',
    defaultWorkflowIds: ['issue-to-pr'],
    primaryAgents: ['db', 'backend', 'qa', 'orchestrator'],
    approvalGates: ['migration', 'pull-request', 'production'],
    defaultGreenLevel: 'release-ready',
    triggers: ['schema change', 'RLS review', 'data quality audit', 'ontology update', 'migration failure'],
    outputs: ['migration plan', 'RLS checklist', 'data audit', 'DB docs sync report'],
    guardrails: ['target project verified', 'PHI risk classified', 'RLS read/write/update/delete matrix required'],
  },
  {
    id: 'ops-finance',
    name: 'Ops/Finance Lane',
    label: '운영/비용',
    objective: 'usage, AI 비용, 운영 리스크, 주간 브리프, 고객지원 후속 조치를 정리한다.',
    defaultWorkflowIds: ['daily-ops', 'prd-to-issue', 'self-improvement'],
    primaryAgents: ['orchestrator', 'planner', 'devops', 'qa'],
    approvalGates: ['plan', 'issue'],
    defaultGreenLevel: 'targeted',
    triggers: ['weekly review', 'cost anomaly', 'support pattern', 'usage trend', 'manual CEO request'],
    outputs: ['weekly ops brief', 'risk list', 'cost analysis', 'follow-up issues'],
    guardrails: ['sensitive data summarized only', 'no PHI in issue body', 'human approves external customer action'],
  },
];

export function getCompanyLane(laneId: CompanyLaneId) {
  return COMPANY_LANES.find((lane) => lane.id === laneId);
}
