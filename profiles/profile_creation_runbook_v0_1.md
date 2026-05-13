# profile_creation_runbook_v0_1

## 생성
```bash
hermes profile create <profile-id> --clone --clone-from default
```

## alias 생성(선택)
```bash
hermes profile alias <profile-id> --name <short>
```

## 최소 검증
```bash
hermes profile list
<short> --help
```

## 주의
- `.env` 민감정보는 커밋 금지
- 역할 분리 위반(과도한 toolset) 방지
