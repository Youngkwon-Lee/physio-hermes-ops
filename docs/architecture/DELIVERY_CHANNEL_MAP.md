# DELIVERY_CHANNEL_MAP

문서 목적: physio-hermes-ops에서 운영하는 주요 Hermes 브리핑/자동화 잡이 **어디로 배달되는지**, 그리고 각 채널의 역할이 무엇인지 문서화한다.

> 주의: 이 문서는 공개 가능한 운영 구조 문서다. private thread ID, token, webhook secret 같은 민감정보는 적지 않는다.

---

## 1. 설계 원칙

1. **브리핑 목적별 전용 채널/쓰레드 우선**  
   서로 다른 성격의 결과물을 한 채널에 섞지 않는다.

2. **읽는 채널과 저장 채널 분리**  
   사용자가 보는 메시지는 짧고 명확해야 하고, 운영 로그/원문/감사 정보는 별도 저장층에 둔다.

3. **브리핑 타입과 채널 목적 일치**  
   뉴스는 뉴스 채널, 운영 브리핑은 비서 채널, 연구 요약은 research 채널처럼 목적이 분명해야 한다.

4. **실패/점검 항목은 별도 관리 가능해야 함**  
   일반 브리핑 채널에 장애 로그를 그대로 뿌리지 않는다.

---

## 2. 현재 채널 맵

| Job Name | Output Type | Primary Delivery Label | Channel Purpose | Backup / Secondary Storage |
|---|---|---|---|---|
| daily-ai-news-briefing | briefing | `discord/news/AI 뉴스 토론` | 매일 아침 AI 뉴스 핵심 브리핑 | Hermes cron output |
| daily-ai-news-discussion-kickoff | kickoff | `discord/news/AI 뉴스 토론` | 브리핑 이후 질문/실험 킥오프 | Hermes cron output |
| daily-rehab-ai-research-brief | research_brief | `discord/research/물리치료·재활 일일 브리핑 토론장` | 재활·물리치료·임상 AI 연구 브리핑 | Hermes cron output |
| overnight-pt-morning-summary | handoff | `discord/research/물리치료·재활 일일 브리핑 토론장` | 밤사이 논의 아침 handoff | Hermes cron output |
| daily-calendar-mail-brief | ops_brief | `discord/비서/아침 일정·메일 요약` | 일정/메일 기반 일일 운영 브리핑 | wiki/raw summary, cron output |
| home-rehab-morning-brief | schedule_brief | `discord/비서/방문재활 일정 관리` | 방문재활 일정 요약 및 실행 준비 | Hermes cron output |
| home-rehab-lunch-recommendation | recommendation | `discord/비서/맛집 추천 기록` | 동선 기반 점심 추천/기록 | Hermes cron output |
| weekly-pt-kpi-brief | kpi_brief | `discord/사업/지원사업 회의실` | PT MVP 운영 지표 공유 | Hermes cron output |
| biz-support-radar-daily | business_radar | `discord/사업/지원사업 레이더 운영 (일일/크론) v2` | 재활·의료AI·스타트업 인접 지원사업 일일 스캔 | Hermes cron output |
| daily-conversation-curator | curator | `discord/비서/장기기억 기록 도우미` | 장기 기억 후보/큐레이션 | Hermes cron output |
| daily-discord-digest | digest | `discord/비서/하루 대화 요약 리포터` | 하루 대화 핵심 요약 | Hermes cron output |
| calendar-auto-classify | maintenance | `local-only` | 사용자-facing delivery 없음 | local runtime only |
| ensure-kinelo-8888-server | watchdog | `local-only` | 사용자-facing delivery 없음 | local runtime only |
| hermes-ops-watchdog | watchdog | `discord/비서/장기기억 기록 도우미` | Hermes gateway/cron 이상만 짧게 알리는 운영 watchdog | Hermes cron output |

---

## 3. 권장 채널 역할 정의

### A. `discord/비서/*`
개인 운영 비서 역할 채널.

적합한 출력:
- 일정 브리핑
- 메일 브리핑
- 하루 요약
- 장기 기억 큐레이션
- 개인 운영 액션 아이템

부적합한 출력:
- 대량 raw research dump
- 디버그 로그 전체
- 시스템 장애 stack trace 원문

---

### B. `discord/research/*`
재활/물리치료/임상 AI 연구 채널.

적합한 출력:
- 일일 연구 브리핑
- 밤사이 연구 handoff
- 논문/연구 아젠다 연결

부적합한 출력:
- 일정 관리 세부사항
- 개인 메일 우선순위 목록

---

### C. `discord/news/*`
AI 뉴스 및 토론 킥오프 채널.

적합한 출력:
- AI 뉴스 핵심 요약
- 토론 질문
- 오늘 확인할 실험 포인트

부적합한 출력:
- 개인 운영 TODO
- 긴 장애 대응 로그

---

### D. `discord/사업/*`
사업/KPI/운영 의사결정 채널.

적합한 출력:
- KPI 브리핑
- 사업성 검토용 운영 지표
- 주간 상태 요약

---

## 4. 읽기층 vs 저장층

### 읽기층 (human-facing)
- Discord thread/message
- 짧고 구조화된 최종 결과만 배달

### 저장층 (ops/audit)
- `~/.hermes/cron/output/`
- wiki raw summary
- docs/reports 내 public-safe sample

원칙:
- 읽기층에는 **핵심 요약**만 보낸다.
- 저장층에는 검증/감사용 metadata를 남길 수 있다.
- private raw data는 저장층이라도 repo 커밋 대상이 아니다.

---

## 5. 향후 확장 가이드

새 cron job을 추가할 때는 최소한 아래 4가지를 먼저 문서화한다.

1. 이 잡의 **목적**은 무엇인가?
2. 이 잡의 **주 사용자/소비 채널**은 어디인가?
3. 이 잡 결과물은 **briefing / kickoff / digest / maintenance** 중 무엇인가?
4. 이 잡의 raw output은 어디에 남기고, 무엇은 남기지 않을 것인가?

권장 절차:
- `cron/registry/jobs.yaml`에 등록
- 이 문서에 delivery label 추가
- 필요한 경우 `docs/specs/BRIEFING_FORMAT_SPEC.md`와 형식 정합성 확인

---

## 6. 운영 메모

- 실제 private 대상 식별자는 Hermes runtime config나 cron state에서 관리한다.
- 이 문서는 구조를 보여주는 공개-safe map이다.
- 채널 목적이 흐려지면 브리핑 품질도 빠르게 무너지므로, 채널 역할 혼합을 최소화한다.
