Run a conservative ChatGPT browser candidate capture on the home desktop.

Goal: inspect the currently visible or recently active ChatGPT conversation in the home desktop browser only when browser-control/screen-read access is available, classify its importance, and write a candidate note only for useful material. Do not scrape full account history.

Home desktop paths:
- Windows workspace: `C:\Users\82106\Documents\brain`
- WSL alias: `/home/yk/brain`
Use the path exposed by the current runtime, but do not use MacBook paths.

Required workflow:
1. Read `operations/chatgpt-screen-capture-routing-v1.md`, `operations/automation-control-center.md`, `operations/second-brain-source-automation-matrix-v1.md`, and `PROMOTION_RULES.md` before writing.
2. If no browser-control/screen-read access is available, do not improvise. Report that ChatGPT browser capture is unavailable on this runtime.
3. Inspect only the current visible ChatGPT conversation or explicit user-provided pointer. Do not open or crawl private ChatGPT history.
4. Before reading full turns, collect only title, URL, and visible/current turn count when available. Search existing `operations/candidates/` and `candidates/` for the exact `source_url`. If the same URL already exists and the turn count has not increased, do not create a duplicate. Report `duplicate_skipped` with the existing file path.
5. If the same URL exists but the turn count increased, update the existing candidate metadata (`last_checked_at`, `last_turn_count`, `new_turn_count`) or create a small `*-update-YYYY-MM-DD.md` note. Do not duplicate the original summary unless the new turns change decisions or next actions.
6. Classify importance using the routing policy: high, medium, low. Use title, URL, and a short recent excerpt first; read full turns only after high classification or explicit user request.
7. For high importance, create a candidate under `operations/candidates/chatgpt-screen-capture-YYYY-MM-DD-<slug>.md` with Summary, Decisions, Next Actions, Reusable Concepts, Suggested Destinations, and bounded Raw Turns if needed as evidence.
8. For medium importance, save only Summary, Decisions, Next Actions, Reusable Concepts, and Suggested Destinations.
9. For low importance, save metadata only or skip.
10. Run `python3 operations/tools/brain_lint.py` or available equivalent and `git diff --check` after file changes.
11. Do not commit if unrelated dirty changes exist. Report files changed, validation, duplicate status, token-saving path used, and whether capture was skipped.
