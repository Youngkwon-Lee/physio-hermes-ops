# AGENT_OS_RUNTIME_SPLIT_V0_1

## Goal

Move Agent OS engine ownership into `physio-hermes-ops` while keeping Mission Control UI in `physio_app`.

## Product Boundary

### `physio_app` keeps

- Mission Control page route
- preview route
- operator UI
- trace visualization
- approval button UX
- Physio auth and org context

### `physio-hermes-ops` owns

- runtime state machine
- harness rules
- workflows
- connectors
- heartbeat and cron ownership
- external execution against GitHub and Vercel

## Extraction Map

### Move to `packages/runtime`

- `physio_app/src/agent-os/agents/registry.ts`
- `physio_app/src/agent-os/lanes/registry.ts`
- `physio_app/src/agent-os/orchestrator/plan.ts`
- `physio_app/src/agent-os/runs/ledger.ts`

### Move to `packages/harness`

- `physio_app/src/agent-os/harness/evals.ts`
- `physio_app/src/agent-os/harness/failures.ts`
- `physio_app/src/agent-os/harness/permissions.ts`
- `physio_app/src/agent-os/harness/traces.ts`

### Move to `packages/workflows`

- `physio_app/src/agent-os/workflows/registry.ts`
- `physio_app/src/agent-os/workflows/prd-to-issue.ts`
- `physio_app/src/agent-os/workflows/issue-to-pr.ts`
- `physio_app/src/agent-os/workflows/issue-to-pr-worker.ts`
- `physio_app/src/agent-os/workflows/pr-to-deploy.ts`
- `physio_app/src/agent-os/workflows/daily-ops.ts`

### Keep in `physio_app`

- `physio_app/src/app/(app)/mission-control/page.tsx`
- `physio_app/src/app/design-concept/mission-control-preview/page.tsx`
- `physio_app/src/features/agent-os/components/mission-control-page.tsx`
- `physio_app/src/features/agent-os/components/agent-office-map.tsx`
- `physio_app/src/features/agent-os/lib/agent-runtime-state.ts`

### Split before moving

- `physio_app/src/features/agent-os/server/mission-control.actions.ts`
- `physio_app/src/features/agent-os/server/integration-readiness.ts`
- `physio_app/src/lib/server/domains/system/agent-os-ops.service.ts`
- `physio_app/src/app/api/cron/agent-os-heartbeat/route.ts`

## Planned Runtime API

- `GET /runs`
- `POST /runs`
- `POST /runs/:id/approve`
- `POST /runs/:id/reject`
- `POST /daily-ops`
- `POST /heartbeat/check`
- `GET /readiness`

## Planned Daemon Jobs

- heartbeat tick
- daily ops tick
- stale run watcher
- self-improvement loop tick

## Extraction Order

1. Create `packages/runtime`, `packages/harness`, `packages/workflows`, `packages/connectors`, `packages/sdk`.
2. Move pure runtime files first.
3. Add Hermes API wrappers.
4. Convert `physio_app` to Hermes SDK consumption.
5. Move daemon ownership out of `physio_app`.
