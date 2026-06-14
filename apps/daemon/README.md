# apps/daemon

Long-running Hermes runtime ownership lives here.

## Planned responsibilities

- heartbeat execution
- cron-triggered daily ops
- stale run detection
- watchdog style failure checks
- recurring Ralph / Ouroboros improvement loops

## Notes

- `apps/daemon` should own scheduling and runtime cadence.
- It should write traces, reports, and state through shared runtime packages.
- Product apps should not run these loops locally.
