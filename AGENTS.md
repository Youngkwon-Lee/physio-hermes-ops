# physio-hermes-ops Agent Router

## Scope
- This is a public-safe operations repo for Hermes multi-profile automation, Mission Control handoff, cron registry, lineage/read-model artifacts, and dashboard surfaces.
- Treat this repo as a release/ops gate for `physio_app`, not as the product app itself.
- Keep project-specific runtime assumptions here; do not promote Hermes-only paths, cron names, or CODEF/Hometax details into global Claude/Codex rules.

## Safety
- Do not commit secrets, credentials, personal identifiers, private tokens, certificates, cookies, or live `.env*` files.
- Never hardcode Hometax, CODEF, Notion, Discord, Supabase, Vercel, OpenAI, Anthropic, SSH, or database credentials. Use environment variables and checked-in `.env.example` placeholders only.
- Do not print secret values during scans or debugging. Report file paths, rule IDs, and counts only.
- Run `uv run python scripts/secret_scan_readiness.py` before claiming security-sensitive changes complete. If `gitleaks` is installed, also run `make secret-scan`.

## Verification
- Default proof for repo wiring changes: `make check`.
- Focused secret proof: `uv run python scripts/secret_scan_readiness.py`.
- Cron registry proof: `HERMES_CRON_PROFILE=<desktop-profile> make cron-registry` when the Hermes CLI is available on the runtime that owns the Home desktop cron jobs.
- Runtime health proof: `uv run python scripts/check_hermes_runtime_health.py` only on the Linux Hermes host; it uses `/home/yk` runtime paths.
- Dashboard/read-model changes should be verified by regenerating the relevant read model or serving the dashboard locally and checking the loaded JSON.

## Editing Rules
- `.runtime/`, `dashboard/derived/*.json`, and most `lineage/*.jsonl` files are generated/runtime artifacts. Do not edit them by hand unless the task explicitly targets fixtures or sample artifacts.
- `deploy/systemd/*.env.example` may contain placeholder variable names only. Never replace placeholders with live values.
- `scripts/hometax_codef_client.py` is credential-sensitive. Any change there must preserve env-only credential loading and include a secret scan.
- The TypeScript package folders are currently source-only package stubs. Do not add root workspace/package-manager behavior unless the task is to wire the workspace explicitly.

## Package And Tooling
- Python scripts run through `uv` using the dependency contract in `pyproject.toml`.
- Use `uv lock` after changing Python dependencies, and prefer `uv run python ...` or `uv run pytest ...` over global interpreter state.
- `make check` runs the local redacted secret scan and the focused Hometax CODEF client tests.
- If a JS/TS workspace is introduced, prefer `pnpm` and add an explicit root workspace configuration.
