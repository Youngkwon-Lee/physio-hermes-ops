# CRON_OPERATIONS

문서 목적: physio-hermes-ops에서 운영하는 Hermes cron job의 **일상 운영 / 수동 실행 / 검증 / 장애 대응** 절차를 표준화한다.

이 문서는 runtime truth 자체를 대체하지 않는다.  
실제 실행 상태의 진실 소스는 항상 다음이다.
- `hermes cron status`
- `hermes cron list`
- `~/.hermes/cron/output/`
- 필요시 gateway / scheduler 로그

---

## 1. 운영 원칙

1. **설계와 런타임을 분리해서 본다**
   - 설계/의도: `cron/registry/jobs.yaml`
   - 실제 상태: Hermes cron runtime state

2. **사용자-facing 브리핑과 운영 로그를 분리한다**
   - Discord에는 짧고 구조화된 결과를 보낸다.
   - 검증/디버깅은 output/log/state에서 한다.

3. **수동 실행은 두 모드가 다르다**
   - `hermes cron run <job_id>` = 다음 scheduler tick에 실행되도록 큐잉
   - `hermes cron run <job_id> --now` = 현재 프로세스에서 즉시 동기 실행

4. **실행 여부는 메시지 문구가 아니라 상태 변화로 검증한다**
   - `last_run_at`
   - `last_status`
   - `next_run_at`
   - output artifact 생성 여부

---

## 2. 기본 점검 순서

cron이 "잘 돌고 있는지" 확인할 때는 아래 순서를 따른다.

### Step 1. Scheduler 상태 확인

```bash
hermes cron status
```

확인할 것:
- gateway/scheduler가 실행 중인지
- active job 개수
- next run 예정 시각

### Step 2. Job 목록 확인

```bash
hermes cron list
```

확인할 것:
- target job의 `job_id`
- schedule
- enabled 여부
- `last_run_at`
- `last_status`
- `next_run_at`

### Step 3. Output artifact 확인

대표 저장 위치:
- `~/.hermes/cron/output/<job_id>/`

확인할 것:
- 오늘 날짜 기준 산출물이 생성됐는지
- 응답이 `[SILENT]`인지 실제 브리핑인지
- Prompt/Response 저장본과 사용자-facing 브리핑의 차이

---

## 3. 수동 실행(run) 의미 정리

### A. Queued run

```bash
hermes cron run <job_id>
```

의미:
- 즉시 실행이 아니다.
- `next_run_at`을 현재 시각 기준으로 당겨 **다음 scheduler tick에서 실행되게 만든다.**

기대되는 검증 순서:
1. run 직후: `next_run_at` 변화 확인
2. scheduler tick 후: `last_run_at`, `last_status` 갱신 확인
3. output artifact 생성 확인

### B. Immediate run

```bash
hermes cron run <job_id> --now
```

의미:
- 현재 프로세스에서 즉시 동기 실행
- output 저장 / delivery / state 갱신이 바로 일어나야 함

기대되는 검증 순서:
1. 명령 반환 성공 확인
2. output artifact 즉시 생성 확인
3. `last_run_at`, `last_status` 즉시 갱신 확인
4. `next_run_at`이 정규 스케줄과 맞는지 확인

---

## 4. 일상 운영 루틴

### A. 아침 점검
추천 체크:

```bash
hermes cron status
hermes cron list
```

추가로 보면 좋은 것:
- 아침 브리핑 계열 job이 오늘 정상 실행됐는지
- `error` 상태 job이 있는지
- 사용자-facing Discord thread에 실제 배달이 되었는지

대상 예시:
- `daily-ai-news-briefing`
- `daily-rehab-ai-research-brief`
- `daily-calendar-mail-brief`
- `overnight-pt-morning-summary`
- `home-rehab-morning-brief`

### B. 저녁 점검
추천 체크:
- end-of-day digest / curator job이 정상 실행됐는지
- local-only maintenance job이 에러 없이 돌고 있는지
- 다음날 아침 브리핑 계열에 영향을 줄 blocker가 없는지

대상 예시:
- `daily-discord-nightly-packet`
- `daily-discord-digest` (직접 스케줄은 paused, nightly packet wrapper가 호출)
- `daily-conversation-curator`
- `calendar-auto-classify`
- watchdog jobs

운영 기준:
- `매일 23:25 디스코드 nightly 패킷`이 action staging, legacy daily digest, postsync를 한 번에 실행한다.
- `매일 23:50 디스코드 하루 요약`과 관련 후처리 잡은 중복 발송 방지를 위해 직접 스케줄이 paused일 수 있다.
- 따라서 하루 요약 상태 판단은 legacy digest job의 `enabled=false`만 보지 말고 nightly packet의 `last_status`, subjob output, postsync 결과를 함께 본다.

### C. watchdog 운영 메모
현재 운영에는 `hermes-ops-watchdog` 같은 경량 watchdog job을 둘 수 있다.

권장 역할:
- `systemctl --user show hermes-gateway` 기준 gateway active/running/PID 이상 감지
- `~/.hermes/cron/jobs.json` 기준 active cron job의 `last_status`, `last_error`, `last_delivery_error` 확인
- `next_run_at`이 현재 시각보다 의미 있게 밀린(overdue) job 감지

운영 원칙:
- watchdog은 **문제가 있을 때만 말하는 silent-by-default** 형태가 적합하다.
- 정상 시에는 empty stdout으로 끝나고, 비정상 시에만 짧은 경고를 보낸다.
- watchdog 자체도 `hermes cron run <job_id> --now`로 즉시 검증하고, output artifact가 `silent (empty output)`인지 함께 확인한다.

주의:
- WSL/host 전체가 꺼져 있으면 watchdog도 같이 멈춘다.
- 따라서 watchdog은 "호스트가 살아 있는 동안의 gateway/cron 이상" 감시에 적합하고, 전체 호스트 다운 감시는 Windows 측 보완이 별도로 필요하다.

---

## 5. 검증 체크리스트

하나의 cron job을 검증할 때 최소한 아래를 본다.

- scheduler가 정상인가?
- job이 enabled 상태인가?
- schedule이 기대한 시간대와 맞는가?
- `last_run_at`이 예상대로 갱신됐는가?
- `last_status`가 `ok` 인가?
- output artifact가 생성됐는가?
- delivery channel에 결과가 실제 도착했는가?
- 결과 format이 `docs/specs/BRIEFING_FORMAT_SPEC.md`와 어긋나지 않는가?

---

## 6. 자주 있는 문제와 해석

### 문제 1. "run 했는데 아무 일도 안 일어난 것 같음"
원인 후보:
- queued run을 immediate run으로 오해함
- scheduler tick을 아직 안 기다림
- output 위치를 안 봄

대응:
1. `hermes cron run <job_id>`인지 `--now`인지 확인
2. `next_run_at`부터 확인
3. output/log/state 확인

### 문제 2. `last_run_at`이 안 바뀜
원인 후보:
- queued run 직후라 아직 실행 전
- job 실패
- scheduler/gateway 문제

대응:
1. `hermes cron status`
2. `hermes cron list`
3. output artifact 확인
4. 필요시 로그 확인

### 문제 3. 결과가 Discord에 안 보임
원인 후보:
- delivery target 문제
- output은 생성됐지만 delivery 실패
- local-only job임

대응:
1. 해당 job의 delivery type 확인
2. output artifact 먼저 확인
3. 필요시 delivery error / gateway log 확인

### 문제 4. 브리핑 품질이 들쭉날쭉함
원인 후보:
- prompt drift
- source signal 부족
- output format spec 부재 또는 미준수

대응:
1. `docs/specs/BRIEFING_FORMAT_SPEC.md` 기준 확인
2. prompt 원본 업데이트 검토
3. signal이 약한 날은 `[SILENT]` 허용 여부 확인

---

## 7. 에러 대응 루프

cron이 실패할 때는 아래 순서로 본다.

1. 증상 기록
   - 어떤 job인지
   - 언제 발생했는지
   - 어떤 출력/미출력이 있었는지

2. 상태 확인
   - `hermes cron status`
   - `hermes cron list`

3. artifact 확인
   - `~/.hermes/cron/output/<job_id>/`

4. run mode 확인
   - queued run이었는지
   - `--now` 였는지

5. 필요한 경우 1회 재현
   - 가능하면 `--now`로 동기 실행 검증

6. 문서 반영
   - 반복 문제라면 runbook/spec/registry 업데이트

---

## 8. 설계 문서와의 연결

cron 관련 변경을 할 때는 아래 문서도 함께 본다.

- `cron/registry/jobs.yaml`
  - job 목적 / 스케줄 / delivery label / 상태

- `docs/architecture/DELIVERY_CHANNEL_MAP.md`
  - 어떤 결과물이 어느 채널로 가는지

- `docs/specs/BRIEFING_FORMAT_SPEC.md`
  - 브리핑 구조 품질 기준

이 3개 문서와 runtime state가 크게 어긋나면, 운영 문서가 stale해진 것으로 본다.

---

## 9. 권장 운영 습관

- cron 추가 시 먼저 registry에 목적과 채널을 문서화한다.
- 개인/민감정보가 섞인 raw output은 repo에 커밋하지 않는다.
- 장애 분석은 최종 메시지가 아니라 output artifact 중심으로 한다.
- channel 목적이 흐려지면 배달 구조부터 다시 정리한다.
- 브리핑 품질 이슈는 prompt보다 먼저 format spec과 signal quality를 점검한다.

---

## 10. 빠른 명령 모음

```bash
# 상태 확인
hermes cron status
hermes cron list

# queued run
hermes cron run <job_id>

# immediate run
hermes cron run <job_id> --now

# pause / resume
hermes cron pause <job_id>
hermes cron resume <job_id>

# output 확인
ls ~/.hermes/cron/output/<job_id>/
```

---

## 11. 한 줄 운영 기준

**"Cron은 CLI 문구가 아니라 state와 output artifact로 검증한다."**
