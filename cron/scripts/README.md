# cron/scripts

Hermes no_agent/script 기반 cron job의 **공개-safe 원본/템플릿** 보관 디렉토리입니다.

원칙:
- 이 폴더는 `~/.hermes/scripts/`의 런타임 실파일을 그대로 백업하는 곳이 아닙니다.
- 공개 저장소이므로 토큰 파일 경로, 개인 이메일 원문, private thread id, 민감한 절대경로는 직접 넣지 않습니다.
- 대신 **운영 의도와 핵심 로직이 보존되는 template/sanitized source**를 둡니다.
- 실제 런타임 파일이 수정되면 이 폴더도 함께 갱신해 drift를 줄입니다.

현재 포함:
- `daily_calendar_mail_brief.py` — 아침 일정·메일 브리핑 스크립트의 공개-safe 버전
- `calendar_auto_classify.py` — 캘린더 자동 분류 스크립트의 공개-safe 버전
- `hermes_ops_watchdog.py` — gateway + cron health를 silent-by-default로 감시하는 no_agent watchdog 스크립트
- `ensure-kinelo-8888.sh` — 8888 로컬 서버 watchdog 스크립트의 공개-safe 버전

권장 운영:
1. 런타임 스크립트 수정
2. 민감정보 제거/일반화
3. 이 디렉토리의 대응 파일 업데이트
4. `python scripts/check_cron_registry.py`로 registry/file drift 확인
5. commit/push
