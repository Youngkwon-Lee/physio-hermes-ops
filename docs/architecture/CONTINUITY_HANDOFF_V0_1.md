# CONTINUITY_HANDOFF_V0_1

## Decision

Hermes, Codex, and Mission Control should not rely on chat memory to continue work.

Every meaningful run should be able to leave a small continuity handoff:

```text
run / tool output
  -> immutable raw handoff
  -> pending memory candidate
  -> human-approved canonical memory
```

This is the minimum bridge between MacBook Codex App work, desktop Hermes work, Mission Control state, and second-brain.

## Roles

| Layer | Owner | Meaning |
| --- | --- | --- |
| Mission Control run | `physio_app` + `physio-hermes-ops` | Current task state, traces, artifacts, approvals |
| Raw handoff | `second-brain` or `ops_knowledge` fallback | Immutable evidence of what happened and what remains |
| Candidate memory | `second-brain` or `ops_knowledge` fallback | A pending note that may be promoted |
| Canonical memory | `second-brain` | Approved durable wiki knowledge |

## Why Raw First

Directly writing canonical memory from an agent run is unsafe.

Raw handoff keeps:

- goal
- completed work
- remaining work
- blockers
- decisions
- related run/thread/branch/PR ids
- proposed memory candidates

Candidate notes can be reviewed later without losing source context.

## V0 Contract

The JSON schema lives in:

```text
docs/specs/continuity_handoff_schema_v0_1.json
```

The capture script lives in:

```text
scripts/capture_continuity_handoff.py
```

Default storage:

```text
${SECOND_BRAIN_DIR}/operations/raw/continuity/YYYY-MM-DD/
${SECOND_BRAIN_DIR}/operations/candidates/continuity/YYYY-MM-DD/
```

If `SECOND_BRAIN_DIR` is not set and `~/brain` does not exist, the script falls back to:

```text
ops_knowledge/
```

Every capture also emits a small event:

```text
continuity_handoff.captured
```

The event can be consumed in two ways:

1. Hermes watches or polls the JSONL event log.
2. Hermes receives `POST /handoff/notify` from the capture script.

This keeps MacBook Codex App work visible to desktop Hermes without granting automatic write access to canonical memory.

## Promotion Rule

V0 may create raw notes and pending candidate notes.

V0 must not automatically promote canonical memory.

Promotion requires a human approval surface such as Mission Control.

## Save Filter

A candidate should exist only when at least one is true:

1. It will be reused in future work.
2. Another agent needs it to continue the project.
3. It records a decision and why it was made.
4. It records a failure pattern to avoid.
5. It defines a shared rule, workflow, or design guide.

Everything else stays raw only.
