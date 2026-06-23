# Hometax Implementation Matrix v0.1

## 1) upstream 조사 결론

| 구분 | 상태 | 근거 |
|---|---|---|
| CODEF 자격증명 저장 | 구현됨 | `korean-jangbu-for-upstream/mcp-server/jangbu_mcp/credentials.py` |
| 홈택스 민원증명 4종 | 구현됨 | `server.py::_codef_fetch_hometax` |
| 2단계 간편인증(`twoWayInfo`) | 구현됨 | `server.py::_codef_fetch_hometax` |
| 은행 거래내역 수집 | 구현됨 | `server.py::_codef_fetch_bank` |
| 카드 이용내역 수집 | 구현됨 | `server.py::_codef_fetch_card` |
| 전자세금계산서 매출/매입 | 문서 흔적만 확인 | `jangbu-jongso/SKILL.md` 예시 있으나 현재 `doc_type` enum엔 없음 |
| 현금영수증 | 문서 흔적만 확인 | 동일 |
| 원천징수/연말정산 | 문서 흔적만 확인 | 동일 |

## 2) 우리 레포 MVP 범위

| 항목 | 이번 포함 | 이유 |
|---|---|---|
| 홈택스 민원증명 4종 | 예 | 현재 실구현이 명확하고 범위가 작음 |
| CODEF 상태 조회 | 예 | 자격증명/설정 문제를 먼저 분리해야 함 |
| dry-run | 예 | 실제 인증정보 없이도 검증 가능해야 함 |
| 대시보드 진입점 | 예 | 사용자 선호가 UI 중심이기 때문 |
| 세금계산서/현금영수증 | 아니오 | 문서-구현 불일치 영역 |
| 홈택스 직접 브라우저 자동화 | 아니오 | 유지보수/보안 비용 큼 |

## 3) 레포 파일 매핑

| 역할 | 파일 |
|---|---|
| 기존 외부조회 예시 | `scripts/k_housing_digest.py` |
| 기존 로컬 HTTP API | `scripts/ops_control_api.py` |
| 기존 정적 대시보드 | `dashboard/index.html` |
| 신규 CODEF 클라이언트 | `scripts/hometax_codef_client.py` |
| 신규 홈택스 상태 CLI | `scripts/k_hometax_digest.py` |
| 신규 운영문서 | `docs/runbook/HOMETAX_MVP_RUNBOOK.md` |

## 4) API 최소안

- `GET /integrations/hometax/status`
- `GET /integrations/hometax/docs`
- `POST /integrations/hometax/fetch`

## 5) 운영 메시지 고정문구

반드시 이렇게 표기:
- "홈택스 MVP (민원증명 4종)"
- "CODEF BYOK 필요"
- "전자세금계산서/현금영수증은 후속 단계"
