import type { AgentId, GreenLevel } from '../../runtime/src/index';

export type EvalSeverity = 'low' | 'medium' | 'high' | 'blocking';

export interface HarnessEval {
  id: string;
  label: string;
  owner: AgentId;
  severity: EvalSeverity;
  command?: string;
  expectation: string;
}

export interface HarnessScenario {
  id: string;
  label: string;
  category: 'planning' | 'permissions' | 'multi-agent' | 'frontend-smoke' | 'db-rls' | 'deploy' | 'self-improvement';
  sourceReference: 'physio-lbp-pilot' | 'claw-code-parity' | 'physio_app';
  requiredGreenLevel: GreenLevel;
  expectation: string;
}

export const BASE_HARNESS_EVALS: HarnessEval[] = [
  {
    id: 'bounded-context-selected',
    label: 'Bounded context selected',
    owner: 'backend',
    severity: 'blocking',
    expectation: 'Server-side changes state one of organization, care-core, activity, scheduling, billing, semantic, or system/platform.',
  },
  {
    id: 'typecheck',
    label: 'TypeScript typecheck',
    owner: 'qa',
    severity: 'blocking',
    command: 'pnpm run typecheck',
    expectation: 'No TypeScript errors.',
  },
  {
    id: 'architecture-guards',
    label: 'Architecture guards',
    owner: 'backend',
    severity: 'high',
    command: 'pnpm run guard:actions && pnpm run guard:domains && pnpm run guard:repositories',
    expectation: 'No route/action/domain/repository boundary regression.',
  },
  {
    id: 'frontend-smoke',
    label: 'Frontend smoke',
    owner: 'frontend',
    severity: 'high',
    expectation: 'Changed screen renders on desktop and mobile without overlap, clipping, or console errors.',
  },
  {
    id: 'migration-human-gate',
    label: 'Migration human gate',
    owner: 'db',
    severity: 'blocking',
    expectation: 'Schema, RLS, and backfill changes require explicit approval before deploy.',
  },
  {
    id: 'preview-smoke',
    label: 'Preview smoke',
    owner: 'devops',
    severity: 'blocking',
    expectation: 'Preview deployment has passing smoke checks before production approval.',
  },
];

export const HARNESS_SCENARIOS: HarnessScenario[] = [
  {
    id: 'prd-to-issue-contract',
    label: 'PRD to issue contract',
    category: 'planning',
    sourceReference: 'physio_app',
    requiredGreenLevel: 'targeted',
    expectation: 'A natural-language mission produces a PRD, acceptance criteria, owner agents, risk notes, and approval gates.',
  },
  {
    id: 'write-boundary-denied',
    label: 'Permission denial path',
    category: 'permissions',
    sourceReference: 'claw-code-parity',
    requiredGreenLevel: 'targeted',
    expectation: 'An agent attempting to write outside its harness boundary receives a structured denial and cannot proceed without approval.',
  },
  {
    id: 'multi-agent-handoff',
    label: 'Multi-agent handoff',
    category: 'multi-agent',
    sourceReference: 'claw-code-parity',
    requiredGreenLevel: 'targeted',
    expectation: 'Planner, Orchestrator, implementation owner, QA, and DevOps exchange artifacts without losing task identity or approval state.',
  },
  {
    id: 'workspace-core-smoke',
    label: 'Workspace core smoke',
    category: 'frontend-smoke',
    sourceReference: 'physio-lbp-pilot',
    requiredGreenLevel: 'workspace',
    expectation: 'Changed clinical workspace flows have route-level smoke coverage for creation, state update, approval, and summary refresh.',
  },
  {
    id: 'rls-boundary-checklist',
    label: 'RLS boundary checklist',
    category: 'db-rls',
    sourceReference: 'physio-lbp-pilot',
    requiredGreenLevel: 'merge-ready',
    expectation: 'Any schema/RLS change records read, write, update/delete, unauthorized, forbidden, and validation-error expectations.',
  },
  {
    id: 'preview-deploy-smoke',
    label: 'Preview deploy smoke',
    category: 'deploy',
    sourceReference: 'physio-lbp-pilot',
    requiredGreenLevel: 'release-ready',
    expectation: 'Production approval is blocked until CI, preview smoke, rollback note, and first-30-minute monitoring plan are present.',
  },
  {
    id: 'harness-improvement-pr',
    label: 'Harness improvement PR',
    category: 'self-improvement',
    sourceReference: 'claw-code-parity',
    requiredGreenLevel: 'merge-ready',
    expectation: 'Repeated failures create a harness/eval/checklist PR rather than directly changing production behavior.',
  },
];
