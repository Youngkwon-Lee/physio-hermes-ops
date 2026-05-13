# OPS Control API Runbook

## 1) 목적
Nautilus 대시보드에서 cron 운영 액션(refresh/pause/resume/finalize)을 안전하게 실행한다.

## 2) 보안 정책
- 기본값: `OPS_CTL_REQUIRE_TOKEN=1` (토큰 필수)
- 권장: **split token**
  - `OPS_CTL_READ_TOKEN`: 히스토리 조회(`/actions/recent`) 전용
  - `OPS_CTL_EXEC_TOKEN`: 실행(`/action`) 전용
- 하위호환: `OPS_CTL_TOKEN` 단일 토큰도 지원(READ/EXEC 공용)
- 토큰은 커밋 금지, 로컬 env 파일로만 주입
- 대시보드는 브라우저 `localStorage` 사용 (`opsCtlReadToken`, `opsCtlExecToken`)

## 3) 로컬 실행
```bash
cd ~/physio-hermes-ops
export OPS_CTL_REQUIRE_TOKEN=1
export OPS_CTL_READ_TOKEN='READ_LONG_RANDOM_TOKEN'
export OPS_CTL_EXEC_TOKEN='EXEC_LONG_RANDOM_TOKEN'
python3 scripts/ops_control_api.py
```

## 4) systemd(user) 등록
```bash
mkdir -p ~/.config/systemd/user ~/.config/physio-hermes-ops
cp deploy/systemd/ops-control-api.service ~/.config/systemd/user/
cp deploy/systemd/ops-control-api.env.example ~/.config/physio-hermes-ops/ops-control-api.env
# env 파일에서 토큰 값 교체
systemctl --user daemon-reload
systemctl --user enable --now ops-control-api.service
systemctl --user status ops-control-api.service --no-pager
```

## 5) 검증
```bash
# health (무인증)
curl -s http://127.0.0.1:8788/health

# recent (READ 토큰 필요)
curl -s -H "Authorization: Bearer $OPS_CTL_READ_TOKEN" \
  http://127.0.0.1:8788/actions/recent

# action dry-run (EXEC 토큰 필요)
curl -s -X POST http://127.0.0.1:8788/action \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $OPS_CTL_EXEC_TOKEN" \
  -d '{"action":"refresh","dry_run":true}'
```

## 6) 감사로그/락
- 감사로그: `lineage/actions_audit.jsonl`
- 실행락: `.runtime/ops_control.lock`
- 동시 실행 요청 시 HTTP `409 busy` 반환

## 7) 토큰 회전(rotate)
```bash
# 1) 새 토큰 생성
python3 - <<'PY'
import secrets
print('OPS_CTL_READ_TOKEN=' + secrets.token_urlsafe(32))
print('OPS_CTL_EXEC_TOKEN=' + secrets.token_urlsafe(32))
PY

# 2) ~/.config/physio-hermes-ops/ops-control-api.env 교체 저장
# 3) 서비스 재시작
systemctl --user restart ops-control-api.service

# 4) 새 토큰으로 API 검증
```
브라우저에서는 `READ 토큰 설정`, `EXEC 토큰 설정` 버튼으로 즉시 갱신.

## 8) 트러블슈팅
- `401 unauthorized (scope=read|exec)`: 해당 scope 토큰 누락/불일치
- `500 server_read_token_not_configured`: READ 토큰 미설정
- `500 server_exec_token_not_configured`: EXEC 토큰 미설정
- `500` with failed command: `actions_audit.jsonl` 및 응답 `results[].stderr` 확인
