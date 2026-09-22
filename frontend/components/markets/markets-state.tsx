'use client'

// Production /markets workspace (T68). Renders the approved v0 geometry with
// live canonical data: three views backed by the read-only P3 APIs, canonical
// enum filters, whole-row internal navigation, and the full degradation
// matrix (loading skeletons, honest empty states, list-level transport
// failure with retry, row-level stale/gap overlays from server flags,
// market-only rows, incomplete books and closed markets). Never imports
// preview fixture data; never calculates probability/edge/fill/settlement.

import { useCallback, useEffect, useRef, useState } from 'react'
import { AlertTriangle, RefreshCw, ShieldCheck } from 'lucide-react'

import { MarketFilters, type GenderFilter, type PhaseFilter } from '@/components/markets/market-filters'
import { MarketRow } from '@/components/markets/market-row'
import { MarketsTabs, type MarketsTabValue } from '@/components/markets/markets-tabs'
import { OpportunityRow } from '@/components/markets/opportunity-row'
import { OpportunityEmptyState } from '@/components/markets/opportunity-empty-state'
import { PaperRow } from '@/components/markets/paper-row'
import { ProductHeader } from '@/components/match/match-header'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { ApiError, getPaperPositions, listMarketOpportunities, listMarkets } from '@/lib/api/client'
import type { CircuitTier, OpportunityAvailabilityDto } from '@/lib/api/types'
import { useMarketStream } from '@/hooks/use-market-stream'
import {
  toMarketRow,
  toOpportunityRow,
  toPaperRow,
  type MarketRowModel,
  type OpportunityRowModel,
  type PaperRowModel,
} from '@/lib/p3-view-models'

const REFRESH_DEBOUNCE_MS = 750
const PAGE_SIZE = 50

type ListStatus = 'loading' | 'ready' | 'error'

export type OpportunitiesState = {
  status: ListStatus
  errorCode: string | null
  rows: OpportunityRowModel[]
  /** Server-provided explanation for an empty tab; null on older payloads. */
  availability: OpportunityAvailabilityDto | null
}

export type ListingsState = {
  status: ListStatus
  errorCode: string | null
  rows: MarketRowModel[]
}

export type PaperState = {
  status: ListStatus
  errorCode: string | null
  open: PaperRowModel[]
  recent: PaperRowModel[]
}

const PAPER_PRIORITY: Record<PaperRowModel['state'], number> = {
  hold: 0,
  exit_pending: 1,
  entry_pending: 2,
  exited: 3,
  missed: 4,
  settled: 5,
}

function errorCodeOf(error: unknown): string {
  if (error instanceof ApiError) return error.code
  return typeof error === 'object' && error !== null && 'code' in error
    ? String((error as { code: unknown }).code)
    : 'internal_error'
}

export type MarketsWorkspaceData = {
  opportunities: OpportunitiesState
  listings: ListingsState
  paper: PaperState
  disabled: boolean
  refetch: () => Promise<void>
}

export function useMarketsWorkspace(): MarketsWorkspaceData {
  const [opportunities, setOpportunities] = useState<OpportunitiesState>({
    status: 'loading',
    errorCode: null,
    rows: [],
    availability: null,
  })
  const [listings, setListings] = useState<ListingsState>({
    status: 'loading',
    errorCode: null,
    rows: [],
  })
  const [paper, setPaper] = useState<PaperState>({
    status: 'loading',
    errorCode: null,
    open: [],
    recent: [],
  })
  const [disabled, setDisabled] = useState(false)
  const debounceRef = useRef<number | null>(null)
  const mountedRef = useRef(true)
  mountedRef.current = true
  useEffect(() => () => { mountedRef.current = false }, [])

  const loadOpportunities = useCallback(async () => {
    try {
      const view = await listMarketOpportunities()
      if (!mountedRef.current) return
      const now = new Date()
      setOpportunities({
        status: 'ready',
        errorCode: null,
        rows: view.rows.map((row) => toOpportunityRow(row, now)),
        availability: view.availability,
      })
    } catch (error) {
      if (!mountedRef.current) return
      if (error instanceof ApiError && error.code === 'p3_disabled') {
        setDisabled(true)
        return
      }
      // Last trusted rows stay visible; the list is marked failed.
      setOpportunities((current) => ({
        status: 'error',
        errorCode: errorCodeOf(error),
        rows: current.rows,
        availability: current.availability,
      }))
    }
  }, [])

  const loadListings = useCallback(async () => {
    try {
      const page = await listMarkets({ page: 1, pageSize: PAGE_SIZE })
      if (!mountedRef.current) return
      const now = new Date()
      setListings({
        status: 'ready',
        errorCode: null,
        rows: page.markets.map((row) => toMarketRow(row, now)),
      })
    } catch (error) {
      if (!mountedRef.current) return
      if (error instanceof ApiError && error.code === 'p3_disabled') {
        setDisabled(true)
        return
      }
      setListings((current) => ({
        status: 'error',
        errorCode: errorCodeOf(error),
        rows: current.rows,
      }))
    }
  }, [])

  const loadPaper = useCallback(async () => {
    try {
      const view = await getPaperPositions()
      if (!mountedRef.current) return
      const now = new Date()
      const mapRow = (row: (typeof view.open)[number]) =>
        toPaperRow(
          row,
          row.player_names ? `${row.player_names[0]} vs. ${row.player_names[1]}` : null,
          now,
        )
      const open = view.open.map(mapRow).sort(
        (a, b) => PAPER_PRIORITY[a.state] - PAPER_PRIORITY[b.state],
      )
      setPaper({
        status: 'ready',
        errorCode: null,
        open,
        recent: view.recent.map(mapRow),
      })
    } catch (error) {
      if (!mountedRef.current) return
      if (error instanceof ApiError && error.code === 'p3_disabled') {
        setDisabled(true)
        return
      }
      setPaper((current) => ({
        status: 'error',
        errorCode: errorCodeOf(error),
        open: current.open,
        recent: current.recent,
      }))
    }
  }, [])

  const refetch = useCallback(async () => {
    await Promise.all([loadOpportunities(), loadListings(), loadPaper()])
  }, [loadOpportunities, loadListings, loadPaper])

  useEffect(() => {
    void refetch()
  }, [refetch])

  const scheduleRefresh = useCallback(() => {
    if (debounceRef.current !== null) window.clearTimeout(debounceRef.current)
    debounceRef.current = window.setTimeout(() => {
      debounceRef.current = null
      void refetch()
    }, REFRESH_DEBOUNCE_MS)
  }, [refetch])

  useEffect(
    () => () => {
      if (debounceRef.current !== null) window.clearTimeout(debounceRef.current)
    },
    [],
  )

  // Stream deltas and gaps only trigger debounced REST refetches of the
  // authoritative lists; nothing is applied from partial stream payloads.
  const stream = useMarketStream({ onGap: scheduleRefresh })
  const firstRender = useRef(true)
  useEffect(() => {
    if (firstRender.current) {
      firstRender.current = false
      return
    }
    scheduleRefresh()
  }, [stream.books, stream.decisions, stream.paper, stream.resolutions, scheduleRefresh])

  return { opportunities, listings, paper, disabled, refetch }
}

function LoadingSkeleton() {
  return (
    <div className="grid gap-3" role="status" aria-busy="true" aria-label="加载中">
      {[0, 1, 2].map((index) => (
        <Card key={index} size="sm">
          <CardContent className="flex min-h-28 items-center gap-4 py-1">
            <div className="h-10 flex-1 animate-pulse rounded-lg bg-muted/60" />
            <div className="h-10 w-24 animate-pulse rounded-lg bg-muted/60" />
            <div className="h-10 w-24 animate-pulse rounded-lg bg-muted/60" />
          </CardContent>
        </Card>
      ))}
      <span className="sr-only">正在加载市场数据</span>
    </div>
  )
}

function ErrorCard({ errorCode, onRetry }: { errorCode: string | null; onRetry: () => void }) {
  return (
    <Card>
      <CardContent role="alert" className="flex min-h-72 flex-col items-center justify-center gap-3 text-center">
        <div className="flex size-10 items-center justify-center rounded-lg bg-destructive/10 text-destructive">
          <AlertTriangle aria-hidden="true" className="size-5" />
        </div>
        <div>
          <h2 className="font-semibold">市场数据加载失败</h2>
          <p className="mt-1 text-sm text-muted-foreground">{errorCode ?? 'internal_error'} · 其他 Tennix 页面仍可继续使用。</p>
        </div>
        <Button variant="outline" onClick={onRetry}>
          <RefreshCw data-icon="inline-start" aria-hidden="true" />
          重试加载
        </Button>
      </CardContent>
    </Card>
  )
}

export function MarketsWorkspace({
  initialView = 'opportunities',
  initialTiers = [],
  initialGender = 'all',
  initialPhase = 'all',
}: {
  initialView?: MarketsTabValue
  initialTiers?: CircuitTier[]
  initialGender?: GenderFilter
  initialPhase?: PhaseFilter
}) {
  const data = useMarketsWorkspace()
  const [view, setView] = useState<MarketsTabValue>(initialView)
  const [tiers, setTiers] = useState<CircuitTier[]>(initialTiers)
  const [gender, setGender] = useState<GenderFilter>(initialGender)
  const [phase, setPhase] = useState<PhaseFilter>(initialPhase)

  function updateUrl(update: (url: URL) => void) {
    const url = new URL(window.location.href)
    url.searchParams.delete('preview')
    update(url)
    window.history.replaceState(null, '', url)
  }

  function selectView(next: MarketsTabValue) {
    setView(next)
    updateUrl((url) => url.searchParams.set('view', next))
  }

  function changeTiers(next: CircuitTier[]) {
    setTiers(next)
    updateUrl((url) => {
      url.searchParams.delete('tier')
      next.forEach((tier) => url.searchParams.append('tier', tier))
    })
  }

  function changeGender(next: GenderFilter) {
    setGender(next)
    updateUrl((url) => {
      if (next === 'all') url.searchParams.delete('gender')
      else url.searchParams.set('gender', next)
    })
  }

  function changePhase(next: PhaseFilter) {
    setPhase(next)
    updateUrl((url) => {
      if (next === 'all') url.searchParams.delete('phase')
      else url.searchParams.set('phase', next)
    })
  }

  function resetFilters() {
    setTiers([])
    setGender('all')
    setPhase('all')
    updateUrl((url) => {
      url.searchParams.delete('tier')
      url.searchParams.delete('gender')
      url.searchParams.delete('phase')
    })
  }

  const hasFilters = tiers.length > 0 || gender !== 'all' || phase !== 'all'
  const filteredListings = data.listings.rows.filter(
    (row) =>
      (tiers.length === 0 || tiers.includes(row.tier as CircuitTier)) &&
      (gender === 'all' || row.gender === gender) &&
      (phase === 'all' ||
        (phase === 'prematch' ? row.phase === 'upcoming' : row.phase === phase)),
  )
  const anyStale =
    data.opportunities.rows.some((row) => row.stale) ||
    filteredListings.some((row) => row.stale)

  return (
    <div className="min-h-screen bg-background text-foreground">
      <ProductHeader active="markets" marketsHref="/markets" />

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
            数据来自 Tennix 只读市场服务；仅用于研究与 Paper 模拟，不涉及真实资金。
          </div>
        </section>

        <MarketsTabs view={view} onSelect={selectView} />

        {data.disabled ? (
          <Card>
            <CardContent className="flex min-h-72 flex-col items-center justify-center gap-3 text-center">
              <div className="flex size-10 items-center justify-center rounded-lg bg-secondary text-primary">
                <ShieldCheck aria-hidden="true" className="size-5" />
              </div>
              <div>
                <h2 className="font-semibold">市场决策支持未启用</h2>
                <p className="mt-1 max-w-md text-sm leading-relaxed text-muted-foreground">
                  p3_disabled · 当前部署未开启 P3 市场数据；比赛信息与助手不受影响。
                </p>
              </div>
            </CardContent>
          </Card>
        ) : (
          <>
            {anyStale ? (
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
              {view === 'opportunities' ? (
                data.opportunities.status === 'loading' ? (
                  <LoadingSkeleton />
                ) : data.opportunities.status === 'error' && data.opportunities.rows.length === 0 ? (
                  <ErrorCard errorCode={data.opportunities.errorCode} onRetry={() => void data.refetch()} />
                ) : data.opportunities.rows.length === 0 ? (
                  <OpportunityEmptyState
                    reason={data.opportunities.availability?.reason ?? null}
                    onViewAllMarkets={() => selectView('all')}
                  />
                ) : (
                  <section className="flex flex-col gap-3" aria-labelledby="opportunities-title">
                    <div className="flex items-end justify-between gap-3">
                      <div>
                        <h2 id="opportunities-title" className="text-lg font-semibold">按决策优先级排序</h2>
                        <p className="mt-1 text-sm text-muted-foreground">直播 BUY 优先，其次是即将开始的价格等待。</p>
                      </div>
                      <span className="font-mono text-xs text-muted-foreground">{data.opportunities.rows.length} 条</span>
                    </div>
                    {data.opportunities.status === 'error' ? (
                      <div role="status" className="flex items-start gap-2 rounded-xl border border-destructive/25 bg-destructive/8 p-4 text-sm text-destructive">
                        <AlertTriangle aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
                        最新刷新失败（{data.opportunities.errorCode}）；以下为最后可信数据。
                      </div>
                    ) : null}
                    <div className="grid gap-3">
                      {data.opportunities.rows.map((row) => (
                        <OpportunityRow key={row.id} opportunity={row} />
                      ))}
                    </div>
                    <div className="flex items-start gap-2 rounded-lg bg-muted/25 p-3 text-xs leading-relaxed text-muted-foreground">
                      <ShieldCheck aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-primary" />
                      BUY 与 WAIT 是研究状态；整行只进入比赛证据页，不执行真实交易。
                    </div>
                  </section>
                )
              ) : view === 'all' ? (
                data.listings.status === 'loading' ? (
                  <LoadingSkeleton />
                ) : (
                  <div className="flex flex-col gap-4">
                    <MarketFilters
                      tiers={tiers}
                      gender={gender}
                      phase={phase}
                      onTiersChange={changeTiers}
                      onGenderChange={changeGender}
                      onPhaseChange={changePhase}
                      onReset={resetFilters}
                    />
                    {data.listings.status === 'error' && data.listings.rows.length === 0 ? (
                      <ErrorCard errorCode={data.listings.errorCode} onRetry={() => void data.refetch()} />
                    ) : filteredListings.length === 0 ? (
                      <Card>
                        <CardContent className="flex min-h-64 flex-col items-center justify-center gap-3 text-center">
                          <div>
                            <h3 className="font-semibold">{hasFilters ? '筛选后无市场' : '供应商暂无市场'}</h3>
                            <p className="mt-1 max-w-md text-sm leading-relaxed text-muted-foreground">
                              {hasFilters
                                ? '尝试移除一个筛选条件，或重置为全部市场。'
                                : '市场源当前没有返回可展示的报价；不会用缓存之外的数据填充。'}
                            </p>
                          </div>
                          {hasFilters ? <Button variant="outline" onClick={resetFilters}>重置筛选</Button> : null}
                        </CardContent>
                      </Card>
                    ) : (
                      <>
                        {data.listings.status === 'error' ? (
                          <div role="status" className="flex items-start gap-2 rounded-xl border border-destructive/25 bg-destructive/8 p-4 text-sm text-destructive">
                            <AlertTriangle aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
                            最新刷新失败（{data.listings.errorCode}）；以下为最后可信数据。
                          </div>
                        ) : null}
                        <div className="grid gap-3" aria-live="polite">
                          {filteredListings.map((row) => (
                            <MarketRow key={row.id} market={row} />
                          ))}
                        </div>
                      </>
                    )}
                  </div>
                )
              ) : data.paper.status === 'loading' ? (
                <LoadingSkeleton />
              ) : data.paper.status === 'error' && data.paper.open.length === 0 && data.paper.recent.length === 0 ? (
                <ErrorCard errorCode={data.paper.errorCode} onRetry={() => void data.refetch()} />
              ) : data.paper.open.length === 0 && data.paper.recent.length === 0 ? (
                <Card>
                  <CardContent className="flex min-h-72 flex-col items-center justify-center gap-3 text-center">
                    <div>
                      <h2 className="font-semibold">暂无 Paper 记录</h2>
                      <p className="mt-1 max-w-md text-sm leading-relaxed text-muted-foreground">
                        只有实际出现过 intent 的研究生命周期才会进入账本。
                      </p>
                    </div>
                  </CardContent>
                </Card>
              ) : (
                <section className="flex flex-col gap-3" aria-labelledby="paper-ledger-title">
                  <div className="flex items-end justify-between gap-3">
                    <div>
                      <h2 id="paper-ledger-title" className="text-lg font-semibold">Paper 生命周期账本</h2>
                      <p className="mt-1 text-sm text-muted-foreground">开放仓位优先；pending、missed 与结算记录均使用不同语义。</p>
                    </div>
                    <span className="font-mono text-xs text-muted-foreground">
                      {data.paper.open.length + data.paper.recent.length} 条
                    </span>
                  </div>
                  <div className="grid gap-3">
                    {[...data.paper.open, ...data.paper.recent].map((row) => (
                      <PaperRow key={row.id} record={row} />
                    ))}
                  </div>
                  <div className="flex items-start gap-2 rounded-lg bg-muted/25 p-3 text-xs leading-relaxed text-muted-foreground">
                    <ShieldCheck aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-primary" />
                    账本只来自 PostgreSQL 权威记录；Paper 结果不代表真实收益。
                  </div>
                </section>
              )}
            </div>
          </>
        )}
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
