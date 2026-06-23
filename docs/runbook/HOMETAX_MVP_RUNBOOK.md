# Hometax MVP Runbook

## 1) 목적
`physio-hermes-ops` 로컬 API/대시보드에서 CODEF BYOK 기반 홈택스 민원증명 4종 MVP를 안전하게 실행한다.

## 2) 이번 MVP 범위
포함:
- 소득금액증명 (`income_proof`)
- 납세증명 (`tax_clearance`)
- 사업자등록증명 (`biz_reg_proof`)
- 부가가치세 과세표준증명 (`vat_base_proof`)

제외:
- 전자세금계산서
- 현금영수증
- 원천징수/연말정산 간소화
- 홈택스 직접 자동화

## 3) 로컬 env 저장 위치
권장 파일:
- `~/.config/physio-hermes-ops/hometax-codef.env`

예시:
```bash
CODEF_CLIENT_ID=...
CODEF_CLIENT_SECRET=...
CODEF_PUBLIC_KEY=...
CODEF_SANDBOX=1
```

## 4) 상태 확인
```bash
python3 scripts/k_hometax_digest.py --check-config-only
```

## 5) API 실행
### status
```bash
curl -s -H "Authorization: Bearer $OPS_CTL_READ_TOKEN" \
  http://127.0.0.1:8788/integrations/hometax/status
```

### docs
```bash
curl -s -H "Authorization: Bearer $OPS_CTL_READ_TOKEN" \
  http://127.0.0.1:8788/integrations/hometax/docs
```

### dry-run
```bash
curl -s -X POST http://127.0.0.1:8788/integrations/hometax/fetch \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $OPS_CTL_EXEC_ADMIN_TOKEN" \
  -d '{"doc_type":"biz_reg_proof","identity":"1234567890","user_name":"홍길동","dry_run":true}'
```

## 6) 실제 2단계 간편인증 흐름
1. `dry_run=false`로 fetch 호출
2. 응답 `stage=waiting_user_auth` 확인
3. 카카오/PASS 승인
4. 응답의 `twoway_info`를 포함해 동일 요청 재호출
5. `stage=completed` 확인

## 7) 실패 케이스
- `missing_required_fields`: doc_type/identity/user_name 누락
- `unsupported doc_type`: 이번 MVP 범위 밖 요청
- `CODEF credentials not configured`: 로컬 키 미설정
- `401 unauthorized`: READ/EXEC 토큰 불일치

## 8) 로그 위치
- 운영 액션/홈택스 fetch 감사로그: `lineage/actions_audit.jsonl`
- 홈택스 env 파일: `~/.config/physio-hermes-ops/hometax-codef.env`

## 9) UI 문구 고정
반드시 다음처럼 안내:
- "홈택스 MVP (민원증명 4종)"
- "CODEF BYOK 필요"
- "전자세금계산서/현금영수증은 후속 단계"
