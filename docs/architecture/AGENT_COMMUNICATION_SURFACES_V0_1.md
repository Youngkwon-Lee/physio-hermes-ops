# AGENT_COMMUNICATION_SURFACES_V0_1

## Decision

For `physio_app` development on the MacBook and Hermes automation on the desktop, do not treat any single chat UI as the system of record.

Use four distinct layers:

1. `Mission Control Web UI` as the canonical human-facing inbox and approval surface
2. `A2A-lite` now, and `A2A` later, for agent-to-agent messaging
3. `MCP` for agent-to-tool and agent-to-context access
4. `second-brain` as durable promoted memory

`Discord` remains a delivery and notification surface, not the canonical state store.

## Why This Is The Right Boundary

The MacBook Codex app is a strong execution surface for coding work, but it is not the best canonical inbox for cross-device orchestration.

Reasons:

- Codex app is optimized for project threads and execution, not multi-agent routing
- Discord is good for alerts and summaries, but poor as the durable control plane
- Mission Control can show run state, approvals, artifacts, and replayable status in one place
- second-brain is the right place for reviewed long-term memory, not transient transport messages

## Surface Roles

| Surface | Primary Role | Not Primary For |
| --- | --- | --- |
| MacBook Codex app | coding, local execution, repo work, operator-driven turns | canonical inbox, long-lived orchestration state |
| desktop Hermes | automation, delegation, monitoring, delayed callbacks | UI-first conversation history |
| Mission Control Web UI | canonical inbox, approvals, run status, artifact review | direct code execution |
| Discord | notifications, summaries, human interrupt path | canonical run state, durable memory |
| second-brain | promoted decisions, reusable knowledge, reviewed continuity | transport, live callback queue |

## Protocol Roles

| Protocol | Purpose | Current Use |
| --- | --- | --- |
| `A2A-lite` | minimal bounded agent-to-agent exchange | validated for `request -> question -> answer -> result` |
| `A2A` | future standard agent-to-agent interoperability | target upgrade path |
| `MCP` | agent-to-tool and agent-to-context access | best practice for structured tool use |
| `Codex App Server` | deep Codex-native client integration | only when building a custom Codex inbox client |

## Best Practice

The preferred architecture is:

```text
Operator
  -> Mission Control Web UI
  -> Hermes run state + artifacts
  -> A2A-lite/A2A bridge
  -> Codex work surface or other agent
  -> callbacks and results back to Mission Control
  -> promotion to second-brain when reviewed
```

`Discord` should subscribe to important state changes:

```text
Mission Control / Hermes
  -> Discord summary or alert
```

not:

```text
Discord
  -> becomes the only source of truth
```

## What We Validated On 2026-06-13

The current bridge already proves the minimum viable multi-agent loop:

- MacBook sender can notify desktop Hermes
- desktop Hermes can return a clarification question
- MacBook can answer in the same conversation
- desktop Hermes can return a final bounded result
- callback delivery can cross devices over Tailscale

This proves the relay layer.

It does **not** yet prove native "desktop message appears automatically inside the MacBook Codex chat UI".

## Canonical Inbox Rule

Until a dedicated Codex-native client is implemented, the canonical place to inspect cross-device status should be Mission Control, not:

- the MacBook Codex chat transcript
- a Discord thread
- a callback JSON file

Callback files and Discord messages are delivery artifacts.
Mission Control should normalize them into run-visible state.

## When To Use Codex App Server

Use `Codex App Server` only if we decide to build a real custom inbox or bridge that must:

- create or resume Codex threads programmatically
- stream turn events
- manage approvals
- persist conversation history outside the stock app UI

Do not use app-server as the first integration step if a relay plus Mission Control already solves the workflow.

## Recommended Near-Term Architecture

1. Keep MacBook Codex app as the primary coding surface for `physio_app`
2. Keep desktop Hermes as the automation and async delegate surface
3. Record cross-device work as Mission Control runs
4. Route result summaries and urgent interrupts to Discord
5. Promote only reviewed continuity to second-brain

## Anti-Patterns

- Treating Discord as the only memory layer
- Treating the Codex app transcript as the canonical multi-agent state store
- Writing directly to canonical memory from raw transport events
- Mixing human-facing summaries with low-level callback payloads
- Binding tool access and agent messaging into one ad hoc protocol

## Next Step

The next implementation target should be:

1. add a Mission Control view for A2A-lite conversations and callback states
2. map callback artifacts into run state and operator-readable summaries
3. keep Discord as a notification mirror
4. defer Codex App Server integration until the Mission Control-centered flow feels insufficient
