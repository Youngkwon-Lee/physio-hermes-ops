# WAVE_SPAWN_RUNBOOK_V0_1

Mini Nautilus 경량 wave spawn 규칙.

## 목적
- 이전 wave 결과에서 best seed를 자동 선택
- 다음 wave 실행 큐(`lineage/wave_queue.jsonl`)를 생성

## 입력
- `lineage/events.jsonl`

## 출력
- `lineage/wave_queue.jsonl` (append)
- `lineage/spawn_state.json` (중복 spawn 방지 상태)

## seed 선택 규칙(v0.1)
- 현재 wave(`wave-N`) 이벤트 중 `score` 최고값 1건 선택
- 해당 이벤트를 `next_wave=wave-(N+1)`의 seed로 사용

## 중복 방지
- `spawn_state.json.last_wave` 이상 wave는 재생성하지 않음

## 실행
```bash
python scripts/spawn_next_wave.py
```

## 스케줄
- cron job: `physio-wave-spawn`
- 기본: 매일 09:15 KST
