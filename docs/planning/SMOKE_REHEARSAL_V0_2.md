# SMOKE_REHEARSAL_V0_2

- mode: profile one-shot with real file actions
- scope: `docs/planning/smoke_sandbox`

## Result Matrix
- physio-planner: PASS (문서 생성 확인)
- physio-frontend: PASS (실제 파일 수정 확인)
- physio-backend: PASS (실제 파일 수정 확인)
- physio-qa: PASS* (CLI timeout 있었지만 산출물 생성 완료)
- physio-orchestrator: PASS* (CLI timeout 있었지만 산출물 생성 완료)

## Artifact Check
- `docs/planning/smoke_sandbox/TASK_SPEC_V2.md` ✅
- `docs/planning/smoke_sandbox/QA_VERIFY_V2.md` ✅
- `docs/planning/smoke_sandbox/ORCH_STATUS_V2.md` ✅

## File Change Check
### ui_mock.tsx
```tsx
export default function MockCard() {
  return (
    <div className="rounded-md border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-900 shadow-sm">
      KPI
    </div>
  )
}
```

### backend_mock.ts
```ts
export function normalizeScore(x: number) {
  return Math.max(0, Math.min(100, x))
}
```

## Observations
1. role별 tool 제한 상태에서도 문서 생성/파일 수정/검증 문서 작성이 모두 동작함.
2. `qa`, `orchestrator`는 one-shot CLI가 timeout(124)으로 끝났지만, 실제 목표 산출물 파일은 생성됨.
3. 따라서 운영 시에는 `hermes chat -q` 타임아웃을 현재보다 길게 주거나 background + poll 패턴이 안정적.

## Next Action
- 다음 웨이브에서 `pnpm lint` + 필요 시 `pnpm exec jest --runInBand`를 실제 실행해 QA 문서(`QA_VERIFY_V2.md`)의 최종 판정 칸까지 채우기.
