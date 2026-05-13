# SMOKE_REHEARSAL_V0_1

- executed_at: 2026-05-13T11:37:59
- mode: hermes profile one-shot (`hermes -p <profile> chat -q`)

## Summary
- physio-planner: PASS
- physio-frontend: PASS
- physio-backend: PASS
- physio-qa: PASS
- physio-orchestrator: PASS

## Per-profile outputs (tail)
### physio-planner
```text
│                                                                              │
│                                   Profile: physio-planner                    │
│                                   11 tools · 135 skills · /help for          │
│                                   commands                                   │
│                                   ⚠ 604 commits behind — run hermes update   │
│                                   to update                                  │
╰──────────────────────────────────────────────────────────────────────────────╯

Query: physio_app nightly용으로 3개 태스크의 acceptance criteria와 verify 
command를 한국어로 짧게 제시해줘. 출력은 bullet만.
Initializing agent...
────────────────────────────────────────

  ┊ 📚 skill     physio-app-automation-overnight-cron-reports  0.6s
 ─  ⚕ Hermes  ───────────────────────────────────────────────────────────────── 
                                                                                
     - 태스크 1: BASE_BRANCH 자동 해석/정렬 고도화 — Acceptance Criteria:       
     nightly 시작 시 current branch → saved-state → main 순서로 base를          
     결정하고, 리포트/로그에 base_branch와 base_source가 항상 기록된다.         
     Verify Command: rg -n "base_branch|base_source"                            
     automation/run_overnight_custom.sh automation/reports/overnight-.md        
     - 태스크 2: READY 없을 때 suggestions-only 리포트 강화 — Acceptance        
     Criteria: READY 0개면 코드 변경 없이 리포트에 오늘의 추천 작업 섹션이      
     생성되고, 최소 Task 파일 점검, low-risk 후보, artifact 기반 후보 3개       
     소제목이 포함된다. Verify Command: rg -n "오늘의 추천 작업|Task 파일       
     점검|low-risk|artifact 기반 후보" automation/reports/overnight-.md         
     - 태스크 3: targeted verify gate 보장 — Acceptance Criteria:               
     SKIP_VERIFY=true여도 각 READY 태스크의 개별 Verify 명령은 실행되고,        
     실패 시 commit/push 없이 리포트에 실패로 남는다. Verify Command: rg -n     
     "Verify:|targeted verify|commit skipped|push skipped|verify failed"        
     automation/overnight.log automation/reports/overnight-*.md                 
                                                                                
 ────────────────────────────────────────────────────────────────────────────── 

Resume this session with:
  hermes --resume 20260513_113125_cc789e

Session:        20260513_113125_cc789e
Duration:       1m 39s
Messages:       4 (1 user, 2 tool calls)
```

### physio-frontend
```text
────────────────────────────────────────

 ─  ⚕ Hermes  ───────────────────────────────────────────────────────────────── 
                                                                                
     다음 5개로 바로 쓰면 돼.                                                   
                                                                                
     1. 로그인 화면 진입 확인                                                   
     - 재현 스텝: 앱 실행 → 로그인 페이지로 이동했을 때 로고, 입력창,           
     로그인 버튼이 정상 노출되는지 확인                                         
                                                                                
     2. 로그인 입력/버튼 동작 확인                                              
     - 재현 스텝: 이메일/비밀번호 입력 → 로그인 버튼 클릭 시 로딩 상태 또는     
     다음 화면 이동이 정상 동작하는지 확인                                      
                                                                                
     3. 메인 대시보드 렌더링 확인                                               
     - 재현 스텝: 로그인 성공 후 메인 화면 진입 → 상단 헤더, 주요 카드,         
     메뉴가 깨짐 없이 표시되는지 확인                                           
                                                                                
     4. 주요 네비게이션 이동 확인                                               
     - 재현 스텝: 사이드바 또는 하단 메뉴에서 다른 메뉴 1개 선택 → 해당         
     페이지로 정상 이동하고 활성 상태가 바뀌는지 확인                           
                                                                                
     5. 기본 반응형/버튼 클릭 가능 여부 확인                                    
     - 재현 스텝: 화면 크기 변경 또는 모바일 뷰 기준으로 확인 → 버튼,           
     입력창, 카드가 겹치지 않고 클릭 가능 상태인지 확인                         
                                                                                
     원하면 내가 이걸 바로                                                      
     - QA 문서용 표 형태                                                        
     - Playwright 스모크 테스트 케이스 형태                                     
     - 체크박스(md) 형태                                                        
     로 바꿔줄게.                                                               
                                                                                
 ────────────────────────────────────────────────────────────────────────────── 

Resume this session with:
  hermes --resume 20260513_113348_bcf21d

Session:        20260513_113348_bcf21d
Duration:       34s
Messages:       2 (1 user, 0 tool calls)
```

### physio-backend
```text
│                                   ⚠ 733 commits behind — run hermes update   │
│                                   to update                                  │
╰──────────────────────────────────────────────────────────────────────────────╯

Query: 백엔드 로직 변경 전 점검 체크리스트 5개를 한국어로 작성하고, 각 항목에 
실패 시 영향 1줄을 붙여줘.
Initializing agent...
────────────────────────────────────────

 ─  ⚕ Hermes  ───────────────────────────────────────────────────────────────── 
                                                                                
     1. 변경 대상 API/서비스의 현재 입력·출력 계약(Request/Response,            
     상태코드, 예외 포맷) 확인                                                  
     실패 시 영향: 프론트나 외부 연동이 갑자기 깨져서 정상 기능이 한꺼번에      
     장애날 수 있음.                                                            
                                                                                
     2. 변경 로직이 영향을 주는 DB 스키마, 쿼리, 트랜잭션 범위 점검             
     실패 시 영향: 데이터 누락·중복·정합성 깨짐이 발생하고 복구 비용이 커질     
     수 있음.                                                                   
                                                                                
     3. 인증/인가 및 권한 분기(admin, staff, user 등) 영향 범위 확인            
     실패 시 영향: 권한 없는 사용자 접근 허용 또는 정상 사용자 차단 같은        
     보안 이슈로 이어질 수 있음.                                                
                                                                                
     4. 기존 테스트 케이스와 추가해야 할 회귀 테스트 포인트 정리                
     실패 시 영향: 로직 수정 후도 겉보기엔 배포되지만, 기존 기능이 조용히       
     망가진 채 운영에 들어갈 수 있음.                                           
                                                                                
     5. 로그, 에러 처리, 모니터링 포인트(알람/메트릭) 유지 여부 확인            
     실패 시 영향: 장애가 나도 원인 추적이 늦어져 대응 시간과 서비스 영향       
     범위가 커질 수 있음.                                                       
                                                                                
 ────────────────────────────────────────────────────────────────────────────── 

Resume this session with:
  hermes --resume 20260513_113433_ac2fba

Session:        20260513_113433_ac2fba
Duration:       25s
Messages:       2 (1 user, 0 tool calls)
```

### physio-qa
```text
+### 3-3. 후속 액션
+- [ ] 수정 필요
+- [ ] 재실행 필요
+- [ ] 머지 가능
+- 메모:
+
+## 4) 로그 경로
+
+- 메인 리포트:
+- 실행 로그:
+- verify 산출물:
+- 스크린샷/첨부:
+- 참고 링크(PR/이슈/액션 런 등):
 ─  ⚕ Hermes  ───────────────────────────────────────────────────────────────── 
                                                                                
     작성해뒀어.                                                                
                                                                                
     파일:                                                                      
     - /home/yk/physio_app/docs/reports/VERIFY_REPORT_TEMPLATE_KO.md            
                                                                                
     구성:                                                                      
     - 실행환경                                                                 
     - 명령                                                                     
     - 결과                                                                     
     - 로그 경로                                                                
                                                                                
     필요하면 내가 바로 다음 단계로                                             
     1) 더 짧은 실전용 버전                                                     
     2) overnight 리포트 스타일에 맞춘 버전                                     
     3) 체크박스형 버전                                                         
     중 하나로 다시 다듬어줄게.                                                 
                                                                                
 ────────────────────────────────────────────────────────────────────────────── 

Resume this session with:
  hermes --resume 20260513_113512_cba405

Session:        20260513_113512_cba405
Duration:       2m 3s
Messages:       22 (1 user, 20 tool calls)
```

### physio-orchestrator
```text
────────────────────────────────────────

 ─  ⚕ Hermes  ───────────────────────────────────────────────────────────────── 
                                                                                
     좋아. 바로 쓰기 좋은 짧은 템플릿으로 줄게.                                 
                                                                                
     GREEN                                                                      
     진행 가능                                                                  
     - 핵심 작업: 정상 진행                                                     
     - 검증 상태: 통과                                                          
     - 블로커: 없음                                                             
     - 아침 액션: 내용 확인 후 머지 여부만 판단                                 
                                                                                
     YELLOW                                                                     
     조건부 진행                                                                
     - 핵심 작업: 일부 진행                                                     
     - 검증 상태: 부분 통과 / 추가 확인 필요                                    
     - 블로커: 경미한 이슈 있음                                                 
     - 아침 액션: 이슈 확인 후 수정 지시 또는 재실행 판단                       
                                                                                
     RED                                                                        
     진행 중단                                                                  
     - 핵심 작업: 완료 못함                                                     
     - 검증 상태: 실패                                                          
     - 블로커: 치명적 이슈 있음                                                 
     - 아침 액션: 블로커 해결 우선, 머지 보류                                   
                                                                                
     원하면 내가 이걸                                                           
     1) 디스코드 보고용 한 줄 버전                                              
     2) 노션/문서용 표 버전                                                     
     으로도 바로 바꿔줄게.                                                      
                                                                                
 ────────────────────────────────────────────────────────────────────────────── 

Resume this session with:
  hermes --resume 20260513_113728_0e1a7c

Session:        20260513_113728_0e1a7c
Duration:       29s
Messages:       2 (1 user, 0 tool calls)
```

## Blockers observed
- none obvious in one-shot responses