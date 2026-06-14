# apps

Hermes runtime entrypoints live here.

This repo currently uses Python scripts, static dashboards, and cron-oriented operational tooling.
The `apps/` directory is the forward path for turning those operational pieces into explicit runtime services.

## Planned apps

- `api/`
  - Mission Control read/write API
  - run ledger query endpoints
  - approval and command endpoints
  - runtime health and readiness endpoints

- `daemon/`
  - heartbeat loop
  - daily ops scheduler
  - stale-run watcher
  - self-improvement / Ralph loop tick ownership

## Rule

- `apps/` should be thin runtime entrypoints.
- Workflow logic belongs in `packages/workflows`.
- State transitions belong in `packages/runtime`.
- Tool adapters belong in `packages/connectors`.
