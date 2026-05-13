# GENERATION_V0_2_RUNBOOK

> 목표: Generation v0.1을 확장해 `PR 링크`와 `승급 이력`을 운영 데이터로 남긴다.

## Added in v0.2
- `links.pr` 자동 매핑 (`scripts/map_lineage_pr_links.py`)
- seed 승급 히스토리 누적 (`lineage/generation_history.jsonl`)

## 1) PR Link Mapping
- 입력: `lineage/events.jsonl`의 `links.commit`
- 처리: commit SHA별 GitHub API 조회로 연관 PR URL 탐색
- 출력: `links.pr` 채움(없으면 null 유지)

## 2) Promotion History
- 입력: `lineage/events.jsonl`
- 처리: 최고 seed 승급 시 history에 append
- 출력:
  - `lineage/generation_state.json` (현재 seed 스냅샷)
  - `lineage/generation_history.jsonl` (누적 계보)

## Commands
```bash
python3 scripts/map_lineage_commit_links.py
python3 scripts/map_lineage_pr_links.py
python3 scripts/promote_generation_seed.py
```

## Minimal Success Criteria
- `events.jsonl` 일부/전체에 `links.commit` 존재
- 가능한 항목의 `links.pr` 보강
- `generation_history.jsonl`에 신규 레코드 append

## Notes
- 퍼블릭 repo 기준 GitHub API 무인증 조회로 동작(레이트리밋 주의)
- v0.3에서 glctl/glhub 형태의 외부 공개 파이프라인으로 확장