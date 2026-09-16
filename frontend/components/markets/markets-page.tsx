'use client'

import { useState, type KeyboardEvent } from 'react'
import { AlertTriangle, RefreshCw, ShieldCheck } from 'lucide-react'

import { AllMarketsView } from '@/components/markets/all-markets-view'
import { OpportunitiesView } from '@/components/markets/opportunities-view'
import { PaperLedgerView } from '@/components/markets/paper-ledger-view'
import { P3PreviewControls } from '@/components/p3/p3-preview-controls'
import type {
  MarketGender,
  MarketsPreviewState,
  MarketView,
  MatchPhase,
  TourTier,
} from '@/components/p3/p3-preview-data'
import { ProductHeader } from '@/components/match/match-header'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { cn } from '@/lib/utils'

const views: Array<{ value: MarketView; label: string; description: string }> = [
  { value: 'opportunities', label: '机会', description: 'BUY 与 WAIT' },
  { value: 'all', label: '全部市场', description: '覆盖与 market-only' },
  { value: 'paper', label: 'Paper', description: '生命周期账本' },
]

const stateOptions: Record<MarketView, Array<{ value: MarketsPreviewState; label: string }>> = {
  opportunities: [
    { value: 'populated', label: 'BUY + WAIT' },
    { value: 'empty', label: '暂无机会' },
    { value: 'partial_stale', label: '部分 stale' },
    { value: 'error', label: '页面错误' },
  ],
  all: [
    { value: 'populated', label: '完整覆盖' },
    { value: 'partial_stale', label: '部分 stale' },
    { value: 'filtered_empty', label: '筛选后为空' },
    { value: 'supplier_empty', label: '供应商无市场' },
    { value: 'error', label: '页面错误' },
  ],
  paper: [
    { value: 'open', label: 'pending / open' },
    { value: 'terminal', label: 'exit / missed / settled' },
    { value: 'resolution_pending', label: '退出确认中' },
    { value: 'empty', label: '暂无记录' },
    { value: 'error', label: '页面错误' },
  ],
}

const defaultState: Record<MarketView, MarketsPreviewState> = {
  opportunities: 'populated',
  all: 'populated',
  paper: 'open',
}

function updateCurrentUrl(update: (url: URL) => void) {
  const url = new URL(window.location.href)
  url.searchParams.set('preview', 'p3')
  update(url)
  window.history.replaceState(null, '', url)
}

export function MarketsPage({
  initialView,
  initialState,
  initialTiers,
  initialGender,
  initialPhase,
}: {
  initialView: MarketView
  initialState: MarketsPreviewState
  initialTiers: TourTier[]
  initialGender: MarketGender | 'all'
  initialPhase: MatchPhase | 'all'
}) {
  const [view, setView] = useState(initialView)
  const [state, setState] = useState(
    stateOptions[initialView].some((option) => option.value === initialState)
      ? initialState
      : defaultState[initialView],
  )
  const [tiers, setTiers] = useState(initialTiers)
  const [gender, setGender] = useState(initialGender)
  const [phase, setPhase] = useState(initialPhase)

  function selectView(nextView: MarketView) {
    const nextState = defaultState[nextView]
    setView(nextView)
    setState(nextState)
    updateCurrentUrl((url) => {
      url.searchParams.set('view', nextView)
      url.searchParams.set('state', nextState)
    })
  }

  function handleTabKeyDown(event: KeyboardEvent<HTMLButtonElement>, index: number) {
    if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') return
    event.preventDefault()
    const offset = event.key === 'ArrowRight' ? 1 : -1
    const nextIndex = (index + offset + views.length) % views.length
    const nextView = views[nextIndex].value
    selectView(nextView)
    document.getElementById(`markets-tab-${nextView}`)?.focus()
  }

  function changePreviewState(_: string, value: string) {
    const nextState = value as MarketsPreviewState
    setState(nextState)
    updateCurrentUrl((url) => url.searchParams.set('state', nextState))
  }

  function changeTiers(nextTiers: TourTier[]) {
    setTiers(nextTiers)
    if (state === 'filtered_empty') setState('populated')
    updateCurrentUrl((url) => {
      url.searchParams.delete('tier')
      nextTiers.forEach((tier) => url.searchParams.append('tier', tier))
      if (state === 'filtered_empty') url.searchParams.set('state', 'populated')
    })
  }

  function changeGender(nextGender: MarketGender | 'all') {
    setGender(nextGender)
    if (state === 'filtered_empty') setState('populated')
    updateCurrentUrl((url) => {
      nextGender === 'all' ? url.searchParams.delete('gender') : url.searchParams.set('gender', nextGender)
      if (state === 'filtered_empty') url.searchParams.set('state', 'populated')
    })
  }

  function changePhase(nextPhase: MatchPhase | 'all') {
    setPhase(nextPhase)
    if (state === 'filtered_empty') setState('populated')
    updateCurrentUrl((url) => {
      nextPhase === 'all' ? url.searchParams.delete('phase') : url.searchParams.set('phase', nextPhase)
      if (state === 'filtered_empty') url.searchParams.set('state', 'populated')
    })
  }

  function resetFilters() {
    setTiers([])
    setGender('all')
    setPhase('all')
    setState('populated')
    updateCurrentUrl((url) => {
      url.searchParams.delete('tier')
      url.searchParams.delete('gender')
      url.searchParams.delete('phase')
      url.searchParams.set('state', 'populated')
    })
  }

  return (
    <div className="min-h-screen bg-background text-foreground">
      <ProductHeader active="markets" marketsHref="/markets?preview=p3" />

      <main id="content" className="mx-auto flex w-full max-w-7xl flex-col gap-6 px-4 py-6 md:px-6 md:py-8">
        <section className="flex flex-col gap-4 border-b pb-6 md:flex-row md:items-end md:justify-between" aria-labelledby="markets-title">
          <div className="max-w-3xl">
            <div className="flex flex-wrap items-center gap-2">
              <p className="font-mono text-xs font-semibold tracking-[0.18em] text-primary">DECISION SUPPORT</p>
              <Badge data-tone="beta" variant="outline">BETA</Badge>
              <Badge variant="secondary">PAPER ONLY</Badge>
            </div>
            <h1 id="markets-title" className="mt-3 text-balance text-3xl font-semibold tracking-[-0.035em] sm:text-4xl">市场决策支持</h1>
            <p className="mt-3 max-w-2xl text-pretty text-sm leading-relaxed text-muted-foreground sm:text-base">
              从机会进入单场证据页，再回到账本复盘；报价、模型与生命周期状态保持可核验且不混写。
            </p>
          </div>
          <div className="flex items-start gap-2 rounded-lg bg-muted/30 p-3 text-xs leading-relaxed text-muted-foreground md:max-w-xs">
            <ShieldCheck aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-primary" />
            Preview 使用固定 fixtures，不请求后端、不连接钱包、不执行真实交易。
          </div>
        </section>

        <P3PreviewControls
          title="Markets · P3 状态预览"
          description="URL 保存 tab、业务状态和叠加筛选。"
          fields={[
            {
              key: 'state',
              label: '业务状态',
              value: state,
              options: stateOptions[view],
            },
          ]}
          onChange={changePreviewState}
        />

        <div className="flex overflow-x-auto rounded-xl border bg-card p-1" role="tablist" aria-label="市场视图">
          {views.map((item, index) => (
            <button
              key={item.value}
              id={`markets-tab-${item.value}`}
              type="button"
              role="tab"
              aria-selected={view === item.value}
              aria-controls={`markets-panel-${item.value}`}
              tabIndex={view === item.value ? 0 : -1}
              onClick={() => selectView(item.value)}
              onKeyDown={(event) => handleTabKeyDown(event, index)}
              className={cn(
                'flex min-h-11 min-w-28 flex-1 flex-col items-center justify-center rounded-lg px-4 py-2 text-sm outline-none transition-colors focus-visible:ring-2 focus-visible:ring-ring',
                view === item.value ? 'bg-secondary font-semibold text-foreground' : 'text-muted-foreground hover:text-foreground',
              )}
            >
              <span>{item.label}</span>
              <span className="hidden text-xs font-normal text-muted-foreground sm:block">{item.description}</span>
            </button>
          ))}
        </div>

        {state === 'partial_stale' ? (
          <div role="status" className="flex items-start gap-2 rounded-xl border border-destructive/25 bg-destructive/8 p-4 text-sm text-destructive">
            <AlertTriangle aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
            部分市场已超过 freshness 阈值。其最后可信数字仍保留，但对应动作已撤销。
          </div>
        ) : null}

        <div
          id={`markets-panel-${view}`}
          role="tabpanel"
          aria-labelledby={`markets-tab-${view}`}
          className="min-h-[28rem]"
        >
          {state === 'error' ? (
            <Card>
              <CardContent role="alert" className="flex min-h-72 flex-col items-center justify-center gap-3 text-center">
                <div className="flex size-10 items-center justify-center rounded-lg bg-destructive/10 text-destructive">
                  <AlertTriangle aria-hidden="true" className="size-5" />
                </div>
                <div>
                  <h2 className="font-semibold">市场页面加载失败</h2>
                  <p className="mt-1 text-sm text-muted-foreground">preview_error · 其他 Tennix 页面仍可继续使用。</p>
                </div>
                <Button
                  variant="outline"
                  onClick={() => {
                    const nextState = defaultState[view]
                    setState(nextState)
                    updateCurrentUrl((url) => url.searchParams.set('state', nextState))
                  }}
                >
                  <RefreshCw data-icon="inline-start" aria-hidden="true" />
                  重试加载
                </Button>
              </CardContent>
            </Card>
          ) : view === 'opportunities' ? (
            <OpportunitiesView state={state} />
          ) : view === 'all' ? (
            <AllMarketsView
              state={state}
              tiers={tiers}
              gender={gender}
              phase={phase}
              onTiersChange={changeTiers}
              onGenderChange={changeGender}
              onPhaseChange={changePhase}
              onReset={resetFilters}
            />
          ) : (
            <PaperLedgerView state={state} />
          )}
        </div>
      </main>

      <footer className="border-t">
        <div className="mx-auto flex max-w-7xl flex-col justify-between gap-2 px-4 py-5 text-sm text-muted-foreground sm:flex-row md:px-6">
          <span>Tennix · 比赛智能，逐分解释</span>
          <span>仅用于研究与 Paper 模拟，不构成财务建议</span>
        </div>
      </footer>
    </div>
  )
}
