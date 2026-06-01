# packages

Reusable Hermes runtime modules live here.

This repo started from scripts, dashboards, and runbooks.
The `packages/` directory is the bridge toward a reusable agent runtime that can support more than one product surface.

## Planned packages

- `runtime/`
- `harness/`
- `workflows/`
- `connectors/`
- `sdk/`

## Rule

- Put state, transitions, and domain contracts here.
- Keep `apps/` as thin entrypoints.
- Keep `dashboard/` as a read model consumer, not the runtime owner.
