# packages/connectors

External system adapters.

## Planned ownership

- GitHub issue and PR publishing
- Vercel preview and production commands
- cron auth and trigger adapters
- local worker execution adapters
- product-specific signal providers
- Kernel API adapters for external product signals (Health Memory remains read-only)

## Split notes

`physio_app` currently mixes runtime logic with Physio queries in:

- `src/features/agent-os/server/mission-control.actions.ts`
- `src/features/agent-os/server/integration-readiness.ts`
- `src/lib/server/domains/system/agent-os-ops.service.ts`

These should be broken into:

- generic Hermes connectors
- product-specific providers such as a Physio ops signal provider

## Codex bridge

The first connector contract is the Codex bridge.

It does not call Codex directly yet.
It defines:

- the worker task shape,
- the remote smoke result shape,
- the Mission Run artifact shape used by Mission Control.

Current files:

- `src/codex-bridge.ts`

The executable smoke command remains:

```bash
python3 scripts/codex_remote_smoke.py --host macbook
```

## Health Memory connector

`src/health-memory-kernel.ts` is the thin Live Run/Hermes adapter for
`POST /api/kernel/v0` with `domain: "memory"`. It never connects to Supabase
or imports `physio_app` internals. The caller supplies the server-only token,
tenant, subject, and provenance; the API enforces the subject allowlist and
patient consent.

For an operator readback without a TypeScript runtime, use:

```bash
HEALTH_MEMORY_BASE_URL=https://kinelo.example \
HEALTH_MEMORY_API_TOKEN=<server-only-token> \
HEALTH_MEMORY_SERVICE_ACCOUNT_ID=svc-hermes \
HEALTH_MEMORY_ORGANIZATION_ID='<organization-uuid>' \
HEALTH_MEMORY_SUBJECT_PERSON_ID='<subject-uuid>' \
python3 scripts/health_memory_read.py --dry-run
```

The default CLI output is a PHI-free count. `--json` is required to emit the
context body to a pipe; never schedule that mode into persistent logs.
