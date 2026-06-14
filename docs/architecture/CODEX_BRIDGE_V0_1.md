# CODEX_BRIDGE_V0_1

## Decision

Hermes should connect to Codex through a worker bridge, not through the Mission Control UI.

Mission Control shows state, starts runs, and records approvals.
Hermes owns orchestration.
The Codex bridge owns code-execution handoff.

## Initial Bridge

Use the bundled Codex CLI on the MacBook as the first worker target:

```text
/Applications/Codex.app/Contents/Resources/codex
```

Do not use Homebrew `codex` as the default bridge binary until the target host proves it is healthy.

## Runtime Flow

```text
Discord or Mission Control
  -> Hermes run
  -> Codex bridge task
  -> remote/local Codex CLI
  -> stdout/file artifact
  -> Hermes run artifact
  -> Mission Control state
```

## V0 Scope

Allowed:

- SSH or local shell health check
- bundled Codex CLI `--version` and `--help`
- non-interactive `codex exec`
- throwaway workdir artifact collection
- JSON summary written by the smoke script

Not allowed yet:

- direct production repo writes
- automatic GitHub push or PR creation
- Codex App Server websocket integration
- Codex SDK as the default path
- direct Mission Control to Codex calls

## Ownership

`physio-hermes-ops` owns:

- bridge docs
- smoke scripts
- worker runbook
- host/path/env contract
- result normalization

`physio_app` owns:

- Mission Control UI
- operator approval
- visual state
- thin Hermes API client

`second-brain` owns:

- durable decisions
- promoted run summaries
- candidate memory review

## Success Contract

A bridge target is usable only when it can prove:

1. transport works,
2. the Codex binary exists,
3. non-interactive execution works,
4. the bridge can collect an artifact.

Until all four pass, Hermes must keep Codex execution in `dry-run` or `blocked` state.

## Runtime Artifact Contract

The bridge has two runtime artifacts:

| Artifact | Kind | Meaning |
| --- | --- | --- |
| Codex Bridge Task | `codex-bridge-task` | The requested host, binary, sandbox, permission stage, prompt, and smoke command |
| Codex Bridge Smoke Result | `codex-bridge-result` | The normalized smoke JSON result that Mission Control can render |

The TypeScript contract lives in:

```text
packages/connectors/src/codex-bridge.ts
```

The runtime artifact kinds are allowed by:

```text
packages/runtime/src/contracts.ts
```

## Failure Classes

| Class | Meaning | Owner |
| --- | --- | --- |
| `transport_failure` | SSH/Tailscale/local command failed before Codex started | ops |
| `binary_failure` | bundled Codex path missing or cannot print help/version | ops |
| `runtime_auth_failure` | Codex starts but cannot run due to login, auth, or onboarding | operator |
| `exec_failure` | `codex exec` failed after startup | bridge |
| `artifact_failure` | command ran, but expected result was not collected | bridge |

## Next Step

Run the smoke script from `physio-hermes-ops`:

```bash
python3 scripts/codex_remote_smoke.py --host macbook
```

For local MacBook verification:

```bash
python3 scripts/codex_remote_smoke.py --local
```
