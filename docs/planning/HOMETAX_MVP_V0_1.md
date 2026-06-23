# Hometax MVP Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** `physio-hermes-ops`에 홈택스/CODEF 연동의 최소 운영형 MVP를 추가해, 대시보드와 로컬 API에서 "설정 상태 확인 → 간편인증 대기 → 민원증명 4종 실행"까지 안전하게 다룰 수 있게 만든다.

**Architecture:** 기존 `scripts/ops_control_api.py`를 그대로 확장해 새 통합 endpoint를 추가한다. 홈택스 본체를 직접 스크래핑하지 않고, 이미 검증된 `korean-jangbu-for` upstream 패턴처럼 BYOK CODEF 클라이언트를 별도 모듈로 분리한다. 민감정보는 repo에 저장하지 않고 로컬 env/keyring/암호화 파일에서만 로드한다.

**Tech Stack:** Python 3, `requests`, 기존 `BaseHTTPRequestHandler` 기반 ops API, 정적 `dashboard/index.html`, 로컬 env 파일

---

## 현재 확인된 사실

- 이 레포는 Python 스크립트 + 정적 대시보드 중심이다.
- 기존 로컬 API는 `scripts/ops_control_api.py` 하나에서 GET/POST endpoint를 처리한다.
- 현재 유사 외부조회 스크립트는 `scripts/k_housing_digest.py` 패턴으로 존재한다.
- `korean-jangbu-for` upstream에서 실제 구현된 홈택스 자동수집 범위는 문서 전체가 아니라 **민원증명 4종**이다.
- 실구현 doc_type:
  - `income_proof`
  - `tax_clearance`
  - `biz_reg_proof`
  - `vat_base_proof`

## 범위 고정 (MVP)

### 이번 MVP에 포함
1. CODEF 설정 상태 조회
2. 홈택스 민원증명 4종 실행 API
3. 2단계 간편인증(`twoWayInfo`) 재호출 지원
4. 대시보드에서 상태 조회 + dry-run/실행 진입점
5. 운영 runbook + env 예시

### 이번 MVP에 제외
- 전자세금계산서 매출/매입 자동수집
- 현금영수증 자동수집
- 원천징수/연말정산 간소화
- 홈택스 직접 브라우저 자동화
- 자격증명 repo 저장

---

## 제안 파일 변경

### Create
- `scripts/hometax_codef_client.py`
- `scripts/k_hometax_digest.py`
- `docs/runbook/HOMETAX_MVP_RUNBOOK.md`
- `deploy/systemd/ops-control-hometax.env.example`

### Modify
- `scripts/ops_control_api.py`
- `dashboard/index.html`
- `README.md`

---

## API 설계 초안

### GET `/integrations/hometax/status`
**목적:** 현재 서버에서 홈택스 연동을 실행할 최소 조건이 갖춰졌는지 확인

**응답 예시**
```json
{
  "ok": true,
  "provider": "codef",
  "configured": true,
  "sandbox": true,
  "available_doc_types": [
    "income_proof",
    "tax_clearance",
    "biz_reg_proof",
    "vat_base_proof"
  ],
  "credential_sources": {
    "client_id": "envfile",
    "client_secret": "envfile",
    "public_key": null
  }
}
```

### POST `/integrations/hometax/fetch`
**권한:** exec

**1단계 요청 예시**
```json
{
  "doc_type": "biz_reg_proof",
  "identity": "1234567890",
  "user_name": "홍길동",
  "login_type": "6",
  "year": "2025",
  "dry_run": false
}
```

**1단계 응답 예시**
```json
{
  "ok": true,
  "stage": "waiting_user_auth",
  "message": "카카오톡 승인 필요",
  "twoway_info": {"jobIndex": 1, "threadIndex": 1}
}
```

**2단계 요청 예시**
```json
{
  "doc_type": "biz_reg_proof",
  "identity": "1234567890",
  "user_name": "홍길동",
  "login_type": "6",
  "twoway_info": {"jobIndex": 1, "threadIndex": 1}
}
```

**완료 응답 예시**
```json
{
  "ok": true,
  "stage": "completed",
  "data_summary": {
    "code": "CF-00000",
    "message": "성공"
  }
}
```

### GET `/integrations/hometax/docs`
**목적:** 대시보드가 지원 범위를 문서화된 방식으로 노출

**응답 예시**
```json
{
  "ok": true,
  "items": [
    {"doc_type": "income_proof", "label": "소득금액증명", "requires_year": true},
    {"doc_type": "tax_clearance", "label": "납세증명", "requires_year": false},
    {"doc_type": "biz_reg_proof", "label": "사업자등록증명", "requires_year": false},
    {"doc_type": "vat_base_proof", "label": "부가가치세 과세표준증명", "requires_year": false}
  ]
}
```

---

## 구현 원칙

1. **BYOK만 허용**
   - `CODEF_CLIENT_ID`
   - `CODEF_CLIENT_SECRET`
   - `CODEF_PUBLIC_KEY` (선택)
   - `CODEF_SANDBOX` (`1|0`)
2. **민감정보 비저장**
   - 요청 body 전체를 audit log에 남기지 말 것
   - identity는 마스킹 후 로그
3. **홈택스 범위 과장 금지**
   - UI/문서에 "민원증명 4종 MVP"라고 명시
4. **2단계 인증 상태머신 유지**
   - `waiting_user_auth`
   - `completed`
   - `error`
5. **dry-run 우선 개발**
   - 실제 자격증명 없이도 curl/UI 검증 가능해야 함

---

## Task 1: CODEF 클라이언트 모듈 분리

**Objective:** 홈택스/CODEF 호출 로직을 `ops_control_api.py`에서 분리 가능한 독립 모듈로 만든다.

**Files:**
- Create: `scripts/hometax_codef_client.py`
- Reference: `/tmp/korean-jangbu-for-upstream/mcp-server/jangbu_mcp/connectors/codef.py`

**Step 1: 새 모듈 스켈레톤 작성**

포함 함수:
```python
load_credentials()
credentials_status()
call_codef(path, body)
fetch_hometax(doc_type, identity, user_name, login_type="6", year=None, twoway_info=None)
mask_identity(value)
```

**Step 2: 지원 문서 타입 상수 정의**
```python
DOC_PATHS = {
    "income_proof": "/v1/kr/public/nt/proof-issue/income-amount",
    "tax_clearance": "/v1/kr/public/nt/proof-issue/tax-clearance",
    "biz_reg_proof": "/v1/kr/public/nt/proof-issue/business-registration",
    "vat_base_proof": "/v1/kr/public/nt/proof-issue/vat-base",
}
```

**Step 3: 자격증명 로더 구현**
- 우선순위:
  1. 환경변수
  2. 로컬 env 파일 (`~/.config/physio-hermes-ops/hometax-codef.env` 같은 별도 파일)
- repo 내부 파일은 읽지 말 것

**Step 4: 2단계 응답 판별 로직 추가**
- `result.code == "CF-03002"`
- 또는 `data.continue2Way == true`

**Step 5: dry-run 모드 지원**
```python
if dry_run:
    return {
        "ok": True,
        "stage": "dry_run",
        "doc_type": doc_type,
        "masked_identity": mask_identity(identity),
    }
```

**Step 6: 최소 수동 검증**
Run:
```bash
python3 - <<'PY'
from scripts.hometax_codef_client import DOC_PATHS, mask_identity
print(sorted(DOC_PATHS))
print(mask_identity('1234567890'))
PY
```
Expected:
- 4개 doc_type 출력
- identity 일부 마스킹 출력

**Step 7: Commit**
```bash
git add scripts/hometax_codef_client.py
git commit -m "feat: add hometax codef client module"
```

---

## Task 2: ops_control_api에 홈택스 상태/실행 endpoint 추가

**Objective:** 기존 로컬 API에 홈택스 상태 조회와 실행 endpoint를 붙인다.

**Files:**
- Modify: `scripts/ops_control_api.py`
- Create: `docs/runbook/HOMETAX_MVP_RUNBOOK.md`

**Step 1: GET endpoint 추가**
`do_GET`에 아래 분기 추가:
- `/integrations/hometax/status`
- `/integrations/hometax/docs`

**Step 2: POST endpoint 추가**
`do_POST`에 아래 분기 추가:
- `/integrations/hometax/fetch`

**Step 3: auth scope 정리**
- `status`, `docs` → read 토큰
- `fetch` → exec 토큰

**Step 4: payload validation 추가**
필수:
- `doc_type`
- `identity`
- `user_name`

선택:
- `login_type`
- `year`
- `twoway_info`
- `dry_run`

**Step 5: 응답 표준화**
```python
{
  "ok": True|False,
  "stage": "dry_run|waiting_user_auth|completed|error",
  "provider": "codef",
  "doc_type": "biz_reg_proof"
}
```

**Step 6: 감사로그 최소화**
- 원문 identity 저장 금지
- `masked_identity`만 기록
- `user_name`도 가능하면 생략 또는 initials 처리

**Step 7: 수동 검증**
Run:
```bash
curl -s http://127.0.0.1:8788/health
curl -s -H "Authorization: Bearer $OPS_CTL_READ_TOKEN" http://127.0.0.1:8788/integrations/hometax/status
curl -s -H "Authorization: Bearer $OPS_CTL_READ_TOKEN" http://127.0.0.1:8788/integrations/hometax/docs
curl -s -X POST http://127.0.0.1:8788/integrations/hometax/fetch \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $OPS_CTL_EXEC_ADMIN_TOKEN" \
  -d '{"doc_type":"biz_reg_proof","identity":"1234567890","user_name":"홍길동","dry_run":true}'
```
Expected:
- status/docs 200
- fetch dry-run 200 with `stage=dry_run`

**Step 8: Commit**
```bash
git add scripts/ops_control_api.py docs/runbook/HOMETAX_MVP_RUNBOOK.md
git commit -m "feat: add hometax integration endpoints"
```

---

## Task 3: 조회 브리핑용 스크립트 추가

**Objective:** 대시보드 외에도 터미널에서 홈택스 연동 상태를 한 번에 점검할 수 있는 요약 스크립트를 만든다.

**Files:**
- Create: `scripts/k_hometax_digest.py`

**Step 1: CLI 인자 정의**
- `--doc-type`
- `--year`
- `--json`
- `--check-config-only`

**Step 2: config-only 모드 구현**
- credentials status 출력
- available doc types 출력
- sandbox 여부 출력

**Step 3: dry-run 실행 모드 구현**
- 민감정보 없이 `--identity-sample` 같은 샘플 값 허용
- 실제 요청 대신 payload shape 확인

**Step 4: 텍스트 출력 포맷 정의**
예시:
```text
[홈택스 MVP 상태]
provider=CODEF sandbox=1 configured=yes
지원 문서: income_proof, tax_clearance, biz_reg_proof, vat_base_proof
실행 모드: config-only
```

**Step 5: 검증**
Run:
```bash
python3 scripts/k_hometax_digest.py --check-config-only
python3 scripts/k_hometax_digest.py --doc-type biz_reg_proof --json
```

**Step 6: Commit**
```bash
git add scripts/k_hometax_digest.py
git commit -m "feat: add hometax digest script"
```

---

## Task 4: 대시보드에 홈택스 카드 추가

**Objective:** 초보자도 바로 이해 가능한 단순 모드로 홈택스 MVP 상태와 실행 진입점을 대시보드에 노출한다.

**Files:**
- Modify: `dashboard/index.html`

**Step 1: 새 섹션 추가**
이름 예시:
- `홈택스 MVP`
- 부제: `민원증명 4종 / CODEF BYOK`

**Step 2: 읽기 상태 카드 배치**
표시 항목:
- configured 여부
- sandbox 여부
- 지원 문서 4종
- 마지막 응답 stage

**Step 3: 안전장치 추가**
실행 전 요약 확인문:
- 대상 문서 종류
- 샌드박스/운영 여부
- 현재 exec role
- 인증 후 재호출 필요 안내

**Step 4: 액션 버튼 추가**
- `상태 새로고침`
- `지원 범위 보기`
- `Dry-run 실행`
- `2단계 승인 후 재실행`

**Step 5: fetch 래퍼 함수 구현**
- `GET /integrations/hometax/status`
- `GET /integrations/hometax/docs`
- `POST /integrations/hometax/fetch`

**Step 6: UX 제약 명시**
UI 문구:
- "전자세금계산서/현금영수증은 이번 MVP 범위 아님"
- "민감정보는 브라우저 저장 금지"

**Step 7: 수동 검증**
- 로컬 브라우저에서 대시보드 오픈
- read token 입력
- 상태 조회 성공 확인
- exec admin token으로 dry-run 성공 확인

**Step 8: Commit**
```bash
git add dashboard/index.html
git commit -m "feat: add hometax mvp dashboard card"
```

---

## Task 5: 운영 문서/환경 예시 정리

**Objective:** 실제 배포/운영 시 필요한 env와 금지사항을 문서로 고정한다.

**Files:**
- Create: `deploy/systemd/ops-control-hometax.env.example`
- Create: `docs/runbook/HOMETAX_MVP_RUNBOOK.md`
- Modify: `README.md`

**Step 1: env example 작성**
포함 변수:
```bash
CODEF_CLIENT_ID=
CODEF_CLIENT_SECRET=
CODEF_PUBLIC_KEY=
CODEF_SANDBOX=1
HOMETAX_CODEF_ENV_FILE=%h/.config/physio-hermes-ops/hometax-codef.env
```

**Step 2: runbook 작성**
섹션:
1. 목적
2. 범위(민원증명 4종 한정)
3. 로컬 env 저장 위치
4. dry-run 검증
5. 실제 간편인증 2단계 흐름
6. 실패 케이스
7. 로그 확인 위치

**Step 3: README 한 줄 연결 추가**
- `docs/runbook/HOMETAX_MVP_RUNBOOK.md`
- `scripts/k_hometax_digest.py`

**Step 4: 검증**
Run:
```bash
grep -n "HOMETAX_MVP_RUNBOOK" README.md
```
Expected:
- README에서 새 runbook 링크 확인

**Step 5: Commit**
```bash
git add deploy/systemd/ops-control-hometax.env.example docs/runbook/HOMETAX_MVP_RUNBOOK.md README.md
git commit -m "docs: add hometax mvp runbook and env example"
```

---

## 문서-구현 불일치 관리 규칙

대시보드/README/Runbook 어디에도 아래처럼 쓰지 말 것:
- "홈택스 전체 자동화 지원"
- "세금계산서/현금영수증까지 지원 완료"

반드시 이렇게 쓸 것:
- "MVP 범위: 홈택스 민원증명 4종"
- "세금계산서·현금영수증 등은 후속 단계"

---

## 검증 시나리오 (완료 기준)

### Smoke A — 설정 없음
- status 호출 시 `configured=false`
- docs 호출은 정상 200
- fetch dry-run은 200
- fetch real run은 400 또는 설정 오류 메시지

### Smoke B — 설정 있음, 실제 인증 전
- status `configured=true`
- fetch 호출 시 `waiting_user_auth`
- `twoway_info` 반환

### Smoke C — 인증 승인 후
- 같은 payload + `twoway_info` 재호출
- `stage=completed`
- 민감데이터 원문이 audit log에 남지 않음

---

## 후속 확장 (이번 범위 아님)

1. 전자세금계산서 매출/매입
2. 현금영수증
3. 원천징수영수증
4. 4대보험 일부
5. 업로드 문서와 자동수집 결과 병합
6. 대시보드에서 결과 파일 다운로드

---

## 추천 구현 순서

1. `scripts/hometax_codef_client.py`
2. `scripts/ops_control_api.py` endpoint 추가
3. `scripts/k_hometax_digest.py`
4. `docs/runbook/HOMETAX_MVP_RUNBOOK.md`
5. `dashboard/index.html`
6. README 연결

---

## 바로 실행할 첫 액션

가장 먼저 할 일:
```bash
python3 - <<'PY'
from pathlib import Path
p = Path('/home/yk/physio-hermes-ops/scripts/ops_control_api.py')
print(p.exists(), p)
PY
```
그 다음 `scripts/hometax_codef_client.py`를 생성하고 dry-run 가능한 최소 골격부터 붙인다.
