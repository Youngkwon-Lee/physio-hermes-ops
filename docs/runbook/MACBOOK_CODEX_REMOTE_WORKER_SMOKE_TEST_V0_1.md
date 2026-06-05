# MACBOOK_CODEX_REMOTE_WORKER_SMOKE_TEST_V0_1

## Goal

Verify that Hermes can call the MacBook bundled Codex CLI as a conservative remote worker.

This is only a smoke test.
It does not connect Mission Control directly to Codex and does not write to real product repos.

## Canonical Codex Path

```bash
/Applications/Codex.app/Contents/Resources/codex
```

Use this path before any Homebrew or shell alias path.

## Manual Checks

### Step -1: enable MacBook SSH

On the MacBook, enable **Remote Login**:

```bash
sudo systemsetup -setremotelogin on
```

Or use macOS Settings:

```text
System Settings -> General -> Sharing -> Remote Login -> On
```

Then confirm the MacBook has a reachable name or address:

```bash
scutil --get LocalHostName
hostname
ipconfig getifaddr en0
```

From the Hermes desktop/WSL host, either use that hostname directly:

```bash
ssh <mac-user>@<mac-local-hostname>.local 'hostname && whoami'
```

or add an SSH alias:

```sshconfig
Host macbook
  HostName <mac-local-hostname>.local
  User <mac-user>
  BatchMode yes
  ConnectTimeout 10
```

### Step 0: transport

```bash
ssh macbook 'hostname && uname -a && whoami'
```

### Step 1: binary health

```bash
ssh macbook '/Applications/Codex.app/Contents/Resources/codex --version'
ssh macbook '/Applications/Codex.app/Contents/Resources/codex --help | head -40'
```

### Step 2: minimum exec

```bash
ssh macbook '/Applications/Codex.app/Contents/Resources/codex exec --sandbox read-only --ephemeral --skip-git-repo-check "Print exactly: CODEX_REMOTE_SMOKE_OK"'
```

### Step 3: throwaway artifact

```bash
ssh macbook 'mkdir -p ~/tmp/codex-smoke && cd ~/tmp/codex-smoke && /Applications/Codex.app/Contents/Resources/codex exec --sandbox workspace-write --ephemeral --skip-git-repo-check "Create a file named result.md containing exactly CODEX_REMOTE_SMOKE_OK" && cat result.md'
```

## Scripted Check

From `physio-hermes-ops`:

```bash
python3 scripts/codex_remote_smoke.py --host macbook
```

Local MacBook check:

```bash
python3 scripts/codex_remote_smoke.py --local
```

Write a JSON result:

```bash
python3 scripts/codex_remote_smoke.py --host macbook --json-out .runtime/codex-smoke/macbook.json
```

## Environment Overrides

```bash
export CODEX_REMOTE_HOST=macbook
export CODEX_REMOTE_BINARY=/Applications/Codex.app/Contents/Resources/codex
export CODEX_REMOTE_WORKDIR='~/tmp/codex-smoke'
```

## Pass Criteria

- transport command exits `0`
- bundled Codex CLI prints version and help
- `codex exec` returns `CODEX_REMOTE_SMOKE_OK`
- throwaway `result.md` contains `CODEX_REMOTE_SMOKE_OK`

The throwaway artifact step uses `--skip-git-repo-check` because `~/tmp/codex-smoke` is intentionally not a product repo.

## Stop Rules

Stop before repo-writing work when:

- SSH/Tailscale is unstable
- Codex asks for login or interactive onboarding
- Codex cannot run non-interactively
- artifact output cannot be collected reliably
- the target is not the expected MacBook

## Failure Classes

| Class | Meaning |
| --- | --- |
| `transport_failure` | SSH/Tailscale/local command failed before Codex started |
| `binary_failure` | Codex path missing or version/help failed |
| `runtime_auth_failure` | Codex likely needs login, onboarding, or approval |
| `exec_failure` | Codex exec ran but failed |
| `artifact_failure` | result artifact missing or wrong |

Common transport hints:

- `Could not resolve hostname macbook`: SSH alias is missing or Tailscale DNS is not available.
- `Connection refused`: the MacBook was reached, but Remote Login/port 22 is off.
- `Permission denied`: key or user authorization is not configured.

## Follow-up After PASS

1. Add a Codex bridge task schema.
2. Store bridge results as Hermes run artifacts.
3. Keep Mission Control as the visual approval surface.
4. Only then test a disposable Git repo patch flow.
