const kpiCards = [
  { label: '오늘 예약', value: '18건', trend: '+2' },
  { label: '신규 문진', value: '6건', trend: '+1' },
  { label: '미완료 차트', value: '3건', trend: '-1' },
]

const loginErrorCopy = '이메일 또는 비밀번호를 다시 확인해 주세요. 계속 안 되면 잠시 후 다시 시도해 주세요.'

function KpiCard({ label, value, trend }: { label: string; value: string; trend: string }) {
  return (
    <article className="flex min-h-[112px] flex-col justify-between rounded-xl border border-slate-200 bg-white px-4 py-4 text-slate-900 shadow-sm">
      <div className="space-y-1">
        <p className="text-sm font-medium text-slate-500">{label}</p>
        <p className="text-2xl font-semibold tracking-tight">{value}</p>
      </div>
      <p className="text-sm font-medium text-emerald-600">전일 대비 {trend}</p>
    </article>
  )
}

export default function SmokeUiMock() {
  return (
    <section className="space-y-6 rounded-2xl bg-slate-50 p-6">
      <div className="max-w-md space-y-3 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="space-y-1">
          <p className="text-sm font-semibold text-slate-900">로그인 오류 상태</p>
          <p className="text-sm leading-6 text-slate-600">
            실패 상태에서도 한 번에 읽히도록 문장을 2개로 제한했다.
          </p>
        </div>

        <div
          aria-live="polite"
          className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm font-medium leading-6 text-rose-700"
          role="alert"
        >
          {loginErrorCopy}
        </div>
      </div>

      <div className="space-y-3">
        <div className="space-y-1">
          <p className="text-sm font-semibold text-slate-900">대시보드 KPI 카드 spacing mock</p>
          <p className="text-sm leading-6 text-slate-600">
            태블릿은 2열, 데스크톱은 3열 grid로 고정하고 카드 내부 padding도 동일하게 맞췄다.
          </p>
        </div>

        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          {kpiCards.map((card) => (
            <KpiCard key={card.label} {...card} />
          ))}
        </div>
      </div>
    </section>
  )
}
