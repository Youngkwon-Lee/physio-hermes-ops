# packages/sdk

Typed client surface for product apps.

## Planned ownership

- list runs
- create runs
- approve and reject gates
- run daily ops
- run heartbeat checks
- fetch readiness

## Primary consumer

- `physio_app` Mission Control UI

## Boundary

- Product apps should call the SDK instead of importing Hermes runtime internals directly.

## Current scope

- shared request and response contracts
- typed HTTP client for Mission Control runtime endpoints
- no direct product UI dependency

Health Memory is intentionally not promoted into this SDK yet. The first
consumer is the thin `packages/connectors/src/health-memory-kernel.ts` adapter;
once Live Run/Hermes has several stable call patterns, the minimal contract can
be promoted here without freezing an oversized abstraction early.
