# cron/scripts

Hermes no_agent/script 기반 cron job의 **공개-safe 원본/템플릿** 보관 디렉토리입니다.

원칙:
- 이 폴더는 `~/.hermes/scripts/`의 런타임 실파일을 그대로 백업하는 곳이 아닙니다.
- 공개 저장소이므로 토큰 파일 경로, 개인 이메일 원문, private thread id, 민감한 절대경로는 직접 넣지 않습니다.
- 대신 **운영 의도와 핵심 로직이 보존되는 template/sanitized source**를 둡니다.
- 실제 런타임 파일이 수정되면 이 폴더도 함께 갱신해 drift를 줄입니다.
- `jobs.yaml`의 `source_state: runtime_snapshot`은 Hermes 런타임 원본을 공개-safe로 정리한 스냅샷입니다.
- `source_state: public_safe_template`은 런타임 원본이 너무 크거나 민감해 공개-safe 골격만 보존한 항목입니다.

현재 포함:
- `daily_calendar_mail_brief.py` — 아침 일정·메일 브리핑 스크립트의 공개-safe 버전
- `home_rehab_morning_brief.py` — 방문재활 아침 브리핑 스크립트의 공개-safe 버전
- `calendar_auto_classify.py` — 캘린더 자동 분류 스크립트의 공개-safe 버전
- `hermes_ops_watchdog.py` — gateway + cron health를 silent-by-default로 감시하는 no_agent watchdog 스크립트
- `kinelo_interview_dropzone_watchdog.py` — Kinelo 인터뷰 Drive dropzone을 처리해 로컬/Drive 노트와 manifest를 생성하는 공개-safe 버전
- `ensure-kinelo-8888.sh` — 8888 로컬 서버 watchdog 스크립트의 공개-safe 버전
- `second_brain_safe_sync.py` — second-brain repo를 dirty 상태에서는 건드리지 않고 clean+behind일 때만 `git pull --ff-only`하는 silent-by-default sync watchdog
- `*_watchdog.py`, `*_git_sync.py`, `*_packet.py`, `desktop-secondbrain-*.sh` — Home desktop Hermes runtime에서 수집한 공개-safe snapshot/template

관련 agent prompt:
- `../prompts/weekly-zotero-literature-ingest.md` — Zotero 접근 가능한 상시 runtime에서 second-brain literature ingest loop를 실행하는 주간 cron prompt
- `../prompts/*.md` 중 `source_state: runtime_snapshot` 항목 — Home desktop Hermes agent prompt를 공개-safe로 정리한 스냅샷

권장 운영:
1. 런타임 스크립트 수정
2. 민감정보 제거/일반화
3. 이 디렉토리의 대응 파일 업데이트
4. `HERMES_CRON_PROFILE=<desktop-profile> make cron-registry`로 registry/file drift 확인
5. commit/push
