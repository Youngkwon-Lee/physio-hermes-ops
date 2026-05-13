# NAUTILUS_STYLE_ROADMAP_V0_1

> Goal: `physio-hermes-ops`를 문서 저장소에서 **Mini Agent OS**로 확장한다.

## Phase 1 (이번 커밋)
- lineage 이벤트 스키마 정의 (`docs/specs/lineage_event_schema_v0_1.json`)
- 실행 기록 JSONL 저장 규칙 정의
- 실행 로그를 요약하는 리포터 스크립트 추가
- 정적 대시보드(`dashboard/index.html`) 추가

## Phase 2
- cron 기반 nightly 자동 집계
- profile별 KPI(score/cost/retry) 집계
- 실패 분류(Class-1/2/3) 자동 태깅

## Phase 3
- PR/커밋 링크 자동 매핑
- generation seed 승급 규칙(best-of-nightly)
- 아침 브리핑 자동 메시지 발송

## 핵심 차별점
- Nautilus처럼 "루프/계보/상태"를 유지하되,
- MVP는 Hermes CLI + 파일 기반으로 가볍게 운영.
