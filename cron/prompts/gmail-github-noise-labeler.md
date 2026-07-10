Triage obvious low-value GitHub notification noise in Gmail for second-brain on the home desktop.

Goal: aggressively but safely down-rank routine automated GitHub notifications before the read-only digest runs. For exact low-risk matches, apply the Gmail label `second-brain/noise-candidate` and move the message to Trash. Do not permanently delete mail, and do not change any message that is not a clear low-risk match.

Home desktop paths:
- Windows workspace: `C:\Users\82106\Documents\brain`
- WSL alias: `/home/yk/brain`
Use the path exposed by the current runtime, but do not use MacBook paths.

Required workflow:
1. Read `operations/automation-control-center.md`, `operations/second-brain-source-automation-matrix-v1.md`, and `operations/source-ingest-registry.md` before acting.
2. Focus only on GitHub notification noise that is safe to down-rank, especially routine automated Encounter Copilot QA comment emails from `[redacted-email]`.
3. Start from a conservative Gmail query that matches the known noise pattern and excludes already-labeled noise, for example mail from `[redacted-email]` containing `Encounter Copilot QA` or `Encounter Copilot QA Generated:` and not already labeled `second-brain/noise-candidate`.
4. Do not touch emails that indicate a failed critical workflow, direct review request, security issue, dependency alert, or active blocker. Skip anything ambiguous.
5. For exact low-risk matches only: apply `second-brain/noise-candidate`, then move the thread to Trash. Do not permanently delete. If the connector cannot Trash safely, fall back to label-only.
6. Keep the run bounded to recent mail and report how many messages were labeled, how many were moved to Trash, and any risky edge cases skipped.
