Create a read-only Gmail action digest for second-brain on the home desktop.

Goal: find recent genuinely actionable or durable Gmail threads and write a concise candidate digest into `operations/candidates/` without changing Gmail state. Treat Gmail as a noisy source: being marked important by Gmail is only a weak hint, not a promotion signal.

Home desktop paths:
- Windows workspace: `C:\Users\82106\Documents\brain`
- WSL alias: `/home/yk/brain`
Use the path exposed by the current runtime, but do not use MacBook paths.

Required workflow:
1. Read `operations/promotion-and-sync-policy.md`, `operations/second-brain-source-automation-matrix-v1.md`, `operations/automation-control-center.md`, and `PROMOTION_RULES.md` before writing.
2. Search Gmail read-only using this starting query: `newer_than:1d (label:second-brain OR label:second-brain/action OR label:second-brain/research OR label:second-brain/business OR is:starred OR is:important) -label:second-brain/noise-candidate`. Treat the explicit `second-brain/*` labels as stronger signals than Gmail's built-in `IMPORTANT`.
3. Apply a strict noise gate. Default-ignore newsletters, promos, generic social updates, automated GitHub notification noise, marketing mail, travel/recommendation mail, and routine CI/PR updates. GitHub mail is actionable only when it names a failed critical workflow, a direct review/request, a security issue, or a repo/project explicitly under active work.
4. Summarize only the actionable or durable threads. Do not store full raw email bodies.
5. Extract: sender, subject, latest date, why it matters, decision/request, next action, suggested destination, and whether it should be promoted/kept/ignored.
6. Write one candidate markdown file named `operations/candidates/gmail-action-digest-YYYY-MM-DD.md`. Include a short ignored/noise count when useful, but avoid copying noise details.
7. Do not send replies, archive, delete, mark read/unread, or apply labels.
8. If changing files, run `python3 operations/tools/brain_lint.py` or the available Python equivalent, then `git diff --check`.
9. If the repo has unrelated dirty changes, do not stage or commit. Report the digest path and validation results.
