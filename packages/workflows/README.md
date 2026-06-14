# packages/workflows

Workflow builders and step definitions.

## Planned ownership

- workflow registry
- PRD to issue planning
- issue to PR planning
- preview and deploy planning
- daily ops planning
- self-improvement planning

## First extraction targets from `physio_app`

- `src/agent-os/workflows/registry.ts`
- `src/agent-os/workflows/prd-to-issue.ts`
- `src/agent-os/workflows/issue-to-pr.ts`
- `src/agent-os/workflows/issue-to-pr-worker.ts`
- `src/agent-os/workflows/pr-to-deploy.ts`
- `src/agent-os/workflows/daily-ops.ts`

## Boundary

- Workflow packages build plans and artifacts.
- They should not publish directly to GitHub or Vercel without connectors.
