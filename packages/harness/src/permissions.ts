import type { AgentId } from '../../runtime/src/index';

export type PermissionEffect = 'allow' | 'deny' | 'approval-required';

export interface HarnessPermissionRule {
  effect: PermissionEffect;
  pattern: string;
  reason: string;
}

export interface HarnessPermissionProfile {
  agentId: AgentId;
  writable: string[];
  approvalRequired: string[];
  forbidden: string[];
  checks: string[];
  stopConditions: string[];
}

export const HARNESS_PERMISSION_PROFILES: Record<AgentId, HarnessPermissionProfile> = {
  orchestrator: {
    agentId: 'orchestrator',
    writable: ['src/agent-os/**', 'docs/AI_NATIVE_*.md', 'docs/planning/**'],
    approvalRequired: ['src/**', 'supabase/**', '.github/**', 'vercel.json'],
    forbidden: ['.env*', '**/*secret*', '**/*phi*'],
    checks: ['pnpm run typecheck'],
    stopConditions: ['cross-domain plan without owner', 'approval boundary unclear'],
  },
  planner: {
    agentId: 'planner',
    writable: ['docs/planning/**', 'docs/PRD_*.md', '.github/ISSUE_TEMPLATE/**'],
    approvalRequired: ['GitHub issue creation'],
    forbidden: ['src/**', 'supabase/**', '.env*'],
    checks: ['acceptance criteria present', 'risk classification present'],
    stopConditions: ['missing product owner decision', 'unbounded feature scope'],
  },
  frontend: {
    agentId: 'frontend',
    writable: ['src/app/**', 'src/features/**/components/**', 'src/components/**', 'src/styles/**'],
    approvalRequired: ['src/features/**/server/**', 'src/lib/server/**'],
    forbidden: ['supabase/**', '.env*', 'src/lib/supabase/database.types.ts'],
    checks: ['pnpm run typecheck', 'pnpm lint', 'browser smoke for changed route'],
    stopConditions: ['needs schema change', 'auth or billing behavior touched'],
  },
  backend: {
    agentId: 'backend',
    writable: ['src/features/**/server/**', 'src/lib/server/domains/**', 'src/lib/server/repositories/**', 'src/lib/schemas/**'],
    approvalRequired: ['src/app/api/**', 'src/lib/supabase/**', 'supabase/**'],
    forbidden: ['.env*', 'src/components/**'],
    checks: ['pnpm run typecheck', 'pnpm run guard:actions', 'pnpm run guard:domains', 'pnpm run guard:repositories'],
    stopConditions: ['bounded context not selected', 'migration required without DB agent'],
  },
  db: {
    agentId: 'db',
    writable: ['supabase/**', 'docs/db/**', 'src/lib/server/repositories/**'],
    approvalRequired: ['RLS policy change', 'production migration', 'data backfill'],
    forbidden: ['.env*', 'src/app/**', 'src/components/**'],
    checks: ['bash scripts/sync_db_docs.sh --source live', 'pnpm run guard:db-docs'],
    stopConditions: ['target Supabase project unclear', 'PHI risk not classified'],
  },
  qa: {
    agentId: 'qa',
    writable: ['src/**/__tests__/**', 'e2e/**', 'docs/checklists/**', 'src/agent-os/evals/**'],
    approvalRequired: ['test waiver', 'release risk acceptance'],
    forbidden: ['supabase/**', '.env*'],
    checks: ['pnpm run typecheck', 'pnpm exec jest --runInBand', 'pnpm run test:e2e:smoke-core'],
    stopConditions: ['repeated flaky failure', 'acceptance criteria ambiguous'],
  },
  devops: {
    agentId: 'devops',
    writable: ['.github/**', 'scripts/**', 'vercel.json', 'src/instrumentation.ts'],
    approvalRequired: ['production deploy', 'rollback', 'secret or env var change'],
    forbidden: ['.env*', 'supabase/migrations/**'],
    checks: ['CI green', 'preview smoke passed', 'rollback path documented'],
    stopConditions: ['production impact unclear', 'monitoring unavailable'],
  },
};

export function getHarnessPermissionProfile(agentId: AgentId) {
  return HARNESS_PERMISSION_PROFILES[agentId];
}
