# GENERATION_V0_8_RUNBOOK

> 목표: lineage timeline에서 generation-close 이벤트를 시각적으로 즉시 구분한다.

## Added in v0.8
- timeline item에 `generation-close-*` run_id 전용 강조 스타일 추가
- 이벤트 본문에 `GEN-CLOSE` 라벨 + 아이콘(♻️) 표기

## Rule
- `run_id`가 `generation-close-`로 시작하면 강조 렌더링
- 기존 active/hover 동작은 유지

## Verify
```bash
python3 -m http.server 8787
# /dashboard/index.html 열어서 timeline에서 generation-close 카드 강조 확인
```
