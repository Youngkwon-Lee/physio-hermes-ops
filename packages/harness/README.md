# packages/harness

Harness rules and evaluation primitives.

## Planned ownership

- permission profiles
- eval definitions
- failure pattern taxonomy
- trace event taxonomy

## First extraction targets from `physio_app`

- `src/agent-os/harness/evals.ts`
- `src/agent-os/harness/failures.ts`
- `src/agent-os/harness/permissions.ts`
- `src/agent-os/harness/traces.ts`

## Boundary

- Harness defines execution policy.
- Product apps only display the resulting state.
