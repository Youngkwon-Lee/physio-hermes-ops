# packages/runtime

Core Agent OS runtime model.

## Planned ownership

- agent registry
- lane registry
- mission run types
- approval state machine
- trace model
- orchestrator plan model

## First extraction targets from `physio_app`

- `src/agent-os/agents/registry.ts`
- `src/agent-os/lanes/registry.ts`
- `src/agent-os/orchestrator/plan.ts`
- `src/agent-os/runs/ledger.ts`

## Boundary

- No product UI here.
- No Physio route/auth concerns here.
- No React or icon dependencies here.

## Current extraction note

The first runtime skeleton intentionally strips UI-only fields such as icon bindings.
Product apps should map agent IDs to icons locally.
