# physio-hermes-ops

Hermes 멀티프로필 운영(physio-*)을 위한 공개 운영 레포입니다.

## 포함 범위 (MVP)
- 프로필 스펙/페르소나 문서
- nightly 운영 runbook/timeout 정책
- smoke rehearsal 산출물 샘플
- lineage 이벤트 로그(JSONL) + 집계 스크립트
- 정적 미니 대시보드(`dashboard/index.html`)

## 디렉토리
- `docs/planning/` : 운영 문서
- `docs/runbook/` : 실행/장애 대응 runbook
- `docs/specs/` : lineage/event 스키마
- `docs/planning/smoke_sandbox/` : 스모크 리허설 샘플 아티팩트
- `profiles/` : 프로필 템플릿(민감정보 제외)
- `automation/` : 스크립트 템플릿(민감정보 제외)
- `lineage/` : 실행 이벤트 로그(JSONL)
- `scripts/` : 집계/리포트 스크립트
- `dashboard/` : 정적 대시보드

## 보안 원칙
- 토큰/키/개인정보는 커밋 금지
- `.env`, `*.key`, `*.pem`, `*.p12`, `*.gpg` 등은 기본 ignore
