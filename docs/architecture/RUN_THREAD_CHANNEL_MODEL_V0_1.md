# RUN_THREAD_CHANNEL_MODEL_V0_1

## Decision

Hermes Ops should treat `run` as the primary execution unit.

`thread` and `channel` are not replacements for `run`.
They are source and reporting context attached to a run.

## Core Model

- `organization`: tenancy and product boundary
- `run`: one concrete goal or operating task
- `thread`: the conversation or working session where the run started or continues
- `channel`: the delivery surface for alerts, approvals, and summaries
- `profile`: the agent role working inside the run

## Practical Meaning

- `run` answers: what work is being done
- `thread` answers: where the work was discussed
- `channel` answers: where updates should go
- `profile` answers: who is acting inside the runtime

## Current API Rule

`POST /runs` may include:

- `source.streamId`
- `source.channelId`
- `source.threadId`
- `source.channelName`
- `source.threadName`

These fields are stored on the run as source metadata.

## Why This Boundary

If thread or channel becomes the primary object, one operational goal can fragment across many messages.
If run remains primary, approvals, PRs, deploy gates, and stale-run detection stay coherent.

## Next Step

1. `physio_app` should send thread/channel metadata when a run starts from a user conversation.
2. Mission Control should show source thread and source channel on the run detail.
3. Hermes reporters should route approval requests back to the recorded thread/channel when available.
