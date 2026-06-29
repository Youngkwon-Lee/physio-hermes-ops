# Current State

이 문서는 `physio-hermes-ops`의 **얇은 실행 상태 카드**입니다.

원칙:
- 장기 구조/운영 원칙은 repo의 `docs/`와 second-brain canonical 문서에 둔다. 홈데스크탑 자동화 기준 경로는 `/home/yk/brain-linux`이며, Windows Obsidian 폴더는 mirror다.
- 이 파일은 다음 agent가 **지금 어떤 운영 작업을 이어야 하는지** 빠르게 파악하는 execution layer다.
- 장문의 운영 로그나 일별 worklog는 여기에 누적하지 않는다.

## Current goal
-

## Working surface
- Repo: `/home/yk/physio-hermes-ops`
- Primary docs:
  - `README.md`
  - `docs/architecture/HERMES_SYSTEM_MAP.md`
  - `docs/architecture/PHYSIO_APP_RUNTIME_SPLIT.md`
  - `docs/runbook/CRON_OPERATIONS.md`
- Related brain docs:
  - `/home/yk/brain-linux/operations/latest-handoff.md`
  - `/home/yk/brain-linux/operations/multi-device-agent-sync-v1.md`
  - `/home/yk/brain-linux/operations/agent-startup-rule-v1.md`
  - `docs/runbook/SECOND_BRAIN_PATH_CONTRACT_V1.md`

## Confirmed
- `physio-hermes-ops`는 Hermes 멀티프로필 운영(physio-*)을 위한 공개 운영 repo다.
- 이 repo는 시스템 맵, runtime split, cron/runbook, profile 템플릿, lineage/event 로그, dashboard read model 관련 자산을 포함한다.
- 현재 구조상 장기 운영 진실은 `docs/architecture/`, `docs/runbook/`, `docs/specs/`에 있고, 이 파일은 재개용 execution note 역할만 한다.
- `PHYSIO_APP_RUNTIME_SPLIT.md` 기준 현재 분리 방향은 **Hermes 쪽은 상태 전이와 artifact 생성만 소유하고, UI 전용 의존성은 physio_app에 남긴다**는 원칙이다.

## Open questions / risks
- 현재 활성 운영 과제(`Current goal`)가 아직 비어 있어, agent가 잘못된 우선순위로 작업을 시작할 위험이 있다.
- 어떤 문서를 이번 세션의 canonical source로 먼저 읽어야 하는지(예: cron 운영, dashboard, runtime split)가 작업 주제별로 달라질 수 있다.
- 공개 repo 특성상 민감정보/실환경 토큰/실제 운영 credential은 절대 이 파일이나 repo 문서에 직접 쓰면 안 된다.

## Next action
- 실제 작업 시작 시 현재 과제를 한 문장으로 `Current goal`에 채운다.
- 작업 주제에 맞는 primary docs 1~3개만 먼저 읽고, 그다음 변경/운영 액션으로 들어간다.
- 작업 종료 시 이 파일과 `/home/yk/brain-linux/operations/latest-handoff.md`를 함께 갱신해 cross-repo continuity를 유지한다.

## Promotion decision
- execution note
