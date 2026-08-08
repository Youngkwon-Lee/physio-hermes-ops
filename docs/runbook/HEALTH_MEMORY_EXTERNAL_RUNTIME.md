# Health Memory external runtime runbook

`physio_app` owns the Health Memory data, consent, and Kernel API boundary.
`physio-hermes-ops` owns the external runtime adapter and operator readback.
The adapter never reads Supabase directly.

## Live Run/Hermes readback

Set these variables in the runtime secret store, not in git or chat:

```text
HEALTH_MEMORY_BASE_URL=https://<physio-app-host>
HEALTH_MEMORY_API_TOKEN=<server-only-machine-token>
HEALTH_MEMORY_SERVICE_ACCOUNT_ID=<service-account-id>
HEALTH_MEMORY_ORGANIZATION_ID=<organization-uuid>
HEALTH_MEMORY_SUBJECT_PERSON_ID=<approved-subject-uuid>
HEALTH_MEMORY_RUNTIME=kinelo-run
```

Run a non-PII configuration check:

```bash
python3 scripts/health_memory_read.py --dry-run
```

Run a readback with a PHI-free summary:

```bash
python3 scripts/health_memory_read.py
```

Use `--json` only when a controlled caller needs the context in memory. Do not
redirect that output into cron logs, lineage files, or analytics.

The server must also configure `KERNEL_API_V0_MEMORY_SUBJECT_IDS` with the same
approved subject UUID. Missing allowlist or missing patient consent returns
`403`; do not retry those responses.

## Ownership

- API/data/policy: `physio_app`
- External adapter/CLI: `physio-hermes-ops`
- Future SDK: `packages/sdk`, after stable call patterns are observed
- MCP: a transport adapter over Kernel API, never a second database path
- Kinelo OS: contract, scope, and registry rules; not a second runtime kernel
