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
