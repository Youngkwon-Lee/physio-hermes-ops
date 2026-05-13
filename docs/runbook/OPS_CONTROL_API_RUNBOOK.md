# OPS Control API Runbook

## 1) 목적
Nautilus 대시보드에서 cron 운영 액션(refresh/pause/resume/finalize)을 안전하게 실행한다.

## 2) 보안 정책
- 기본값: `OPS_CTL_REQUIRE_TOKEN=1` (토큰 필수)
- 토큰은 커밋 금지, 로컬 env 파일로만 주입
- 대시보드는 브라우저 `localStorage.opsCtlToken` 사용

## 3) 로컬 실행
```bash
cd ~/physio-hermes-ops
export OPS_CTL_TOKEN='YOUR_LONG_RANDOM_TOKEN'
export OPS_CTL_REQUIRE_TOKEN=1
python3 scripts/ops_control_api.py
```

## 4) systemd(user) 등록
```bash
mkdir -p ~/.config/systemd/user ~/.config/physio-hermes-ops
cp deploy/systemd/ops-control-api.service ~/.config/systemd/user/
cat > ~/.config/physio-hermes-ops/ops-control-api.env <<'EOF'
OPS_CTL_TOKEN=YOUR_LONG_RANDOM_TOKEN
EOF
systemctl --user daemon-reload
systemctl --user enable --now ops-control-api.service
systemctl --user status ops-control-api.service --no-pager
```

## 5) 검증
```bash
curl -s http://127.0.0.1:8788/health
curl -s -H "Authorization: Bearer $OPS_CTL_TOKEN" http://127.0.0.1:8788/actions/recent
curl -s -X POST http://127.0.0.1:8788/action \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $OPS_CTL_TOKEN" \
  -d '{"action":"refresh","dry_run":true}'
```

## 6) 감사로그/락
- 감사로그: `lineage/actions_audit.jsonl`
- 실행락: `.runtime/ops_control.lock`
- 동시 실행 요청 시 HTTP `409 busy` 반환

## 7) 트러블슈팅
- `401 unauthorized`: 토큰 누락/불일치
- `500 server_token_not_configured`: 서버 env에 `OPS_CTL_TOKEN` 미설정
- `500` with failed command: `actions_audit.jsonl` 및 응답의 `results[].stderr` 확인
