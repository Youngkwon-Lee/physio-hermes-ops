export type GreenLevel =
  | 'typecheck'
  | 'package'
  | 'workspace'
  | 'targeted'
  | 'merge-ready'
  | 'release-ready';

export type WorkflowId =
  | 'daily-ops'
  | 'prd-to-issue'
  | 'issue-to-pr'
  | 'pr-to-deploy'
  | 'self-improvement';

export interface MissionArtifact {
  label: string;
  value: string;
  kind?:
    | 'summary'
    | 'prd'
    | 'issue-draft'
    | 'github-issue'
    | 'issue-to-pr-plan'
    | 'branch-plan'
    | 'check-plan'
    | 'pr-draft'
    | 'worker-run'
    | 'permission-audit'
    | 'check-result'
    | 'pull-request'
    | 'preview-deploy'
    | 'smoke-report'
    | 'rollback-plan'
    | 'monitoring-plan'
    | 'production-deploy'
    | 'release-note'
    | 'ops-brief';
  metadata?: Record<string, string | number | boolean | null>;
}
