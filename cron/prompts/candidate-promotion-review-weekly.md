Run a weekly candidate promotion review for second-brain on the home desktop.

Goal: review recent second-brain candidates, including ChatGPT screen captures, mobile captures, Codex deltas, Gmail digests, and other candidate notes, then recommend the smallest safe promotions into canonical docs. Do not directly edit canonical docs unless the target and patch are obvious, low-risk, and fully supported by the candidate summary. Prefer review output and apply-ready notes over broad automatic promotion.

Home desktop paths:
- Windows workspace: `C:\Users\82106\Documents\brain`
- WSL alias: `/home/yk/brain`
Use the path exposed by the current runtime, but do not use MacBook paths.

Required workflow:
1. Read `operations/promotion-and-sync-policy.md`, `operations/weekly-promotion-review-manual-apply.md`, `operations/chatgpt-screen-capture-routing-v1.md`, `operations/ingest-checklist.md`, `operations/automation-control-center.md`, and `PROMOTION_RULES.md` before judging candidates.
2. Check `git status --short --branch`. If dirty, do not stage or commit unrelated user changes. Continue read-only where possible.
3. Review recent candidate files from the last 14 days under `operations/candidates/`, `candidates/`, and `candidates/captures/` (iOS Back Tap screenshot OCR captures), prioritizing files with `importance: high`, `route: raw_candidate`, `route: summary_only`, or clear `Next Actions` / `Decisions` sections. For `candidates/captures/` items, OCR text may contain transcription noise — classify against the screenshot's apparent intent, and prefer `discard` for low-signal screens (home screens, app lists) and `promote`/`keep` only for durable reference or idea content.
4. For ChatGPT screen captures, read only Summary / Decisions / Next Actions / Reusable Concepts first. Read Raw Turns only if the summary is ambiguous or evidence is needed.
5. Classify each candidate as `promote`, `keep`, `discard`, or `needs-human-review`. Promote only when the signal is durable, non-sensitive, and the target document is clear.
6. If a promotion is recommended, create or update an apply-ready review note under `operations/auto-apply-notes/` with: target doc, confidence, evidence candidate path, proposed patch gist, and exact next command/action. Do not dump raw transcripts.
7. If making any file changes, run `python3 operations/tools/brain_lint.py` or the available Python equivalent, then `git diff --check`. Report exact failures.
8. Final output should include reviewed candidate count, high-priority candidates, recommended promotions, kept/discarded items, files changed, validation result, and whether any human decision is needed.
