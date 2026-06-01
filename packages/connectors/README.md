# packages/connectors

External system adapters.

## Planned ownership

- GitHub issue and PR publishing
- Vercel preview and production commands
- cron auth and trigger adapters
- local worker execution adapters
- product-specific signal providers

## Split notes

`physio_app` currently mixes runtime logic with Physio queries in:

- `src/features/agent-os/server/mission-control.actions.ts`
- `src/features/agent-os/server/integration-readiness.ts`
- `src/lib/server/domains/system/agent-os-ops.service.ts`

These should be broken into:

- generic Hermes connectors
- product-specific providers such as a Physio ops signal provider
