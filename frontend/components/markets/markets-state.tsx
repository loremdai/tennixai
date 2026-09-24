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
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { ApiError, getPaperPositions, listMarketOpportunities, listMarkets } from '@/lib/api/client'
import { userFacingApiError } from '@/lib/api/user-facing-errors'
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
const LISTING_QUOTE_REFRESH_INTERVAL_MS = 1_000
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
  page: number
  total: number
  loadingMore: boolean
}

export type PaperState = {
  status: ListStatus
  errorCode: string | null
  open: PaperRowModel[]
  recent: PaperRowModel[]
}

const PAPER_PRIORITY: Record<PaperRowModel['state'], number> = {
  hold: 0,
  exit_missed: 1,
  exit_pending: 2,
  entry_pending: 3,
  exited: 4,
  missed: 5,
  settled: 6,
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
  loadMoreListings: () => void
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
    page: 0,
    total: 0,
    loadingMore: false,
  })
  const [paper, setPaper] = useState<PaperState>({
    status: 'loading',
    errorCode: null,
    open: [],
    recent: [],
  })
  const [disabled, setDisabled] = useState(false)
  const debounceRef = useRef<number | null>(null)
  const listingsDebounceRef = useRef<number | null>(null)
  const lastListingsRefreshAtRef = useRef(0)
  const loadedListingsPageRef = useRef(0)
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

  const loadListings = useCallback(async (
    options: { throughPage?: number; append?: boolean } = {},
  ) => {
    const throughPage = options.throughPage ?? Math.max(loadedListingsPageRef.current, 1)
    const append = options.append ?? false
    if (append && throughPage !== loadedListingsPageRef.current + 1) return
    if (append) {
      setListings((current) => ({ ...current, loadingMore: true, errorCode: null }))
    }
    try {
      const firstPage = append ? throughPage : 1
      const pages = []
      for (let page = firstPage; page <= throughPage; page += 1) {
        pages.push(await listMarkets({ page, pageSize: PAGE_SIZE }))
      }
      if (!mountedRef.current) return
      const now = new Date()
      const incoming = pages.flatMap((page) => page.markets.map((row) => toMarketRow(row, now)))
      const total = pages[0]?.total ?? 0
      loadedListingsPageRef.current = throughPage
      setListings((current) => {
        const combined = append ? [...current.rows, ...incoming] : incoming
        const unique = new Map(combined.map((row) => [row.id, row]))
        return {
          status: 'ready',
          errorCode: null,
          rows: [...unique.values()],
          page: throughPage,
          total,
          loadingMore: false,
        }
      })
    } catch (error) {
      if (!mountedRef.current) return
      if (error instanceof ApiError && error.code === 'p3_disabled') {
        setDisabled(true)
        setListings((current) => ({ ...current, loadingMore: false }))
        return
      }
      setListings((current) => ({
        status: 'error',
        errorCode: errorCodeOf(error),
        rows: current.rows,
        page: current.page,
        total: current.total,
        loadingMore: false,
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
    await Promise.all([
      loadOpportunities(),
      loadListings({ throughPage: Math.max(loadedListingsPageRef.current, 1) }),
      loadPaper(),
    ])
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

  const scheduleListingsRefresh = useCallback(() => {
    if (listingsDebounceRef.current !== null) return
    const elapsed = Date.now() - lastListingsRefreshAtRef.current
    const delay = Math.max(0, LISTING_QUOTE_REFRESH_INTERVAL_MS - elapsed)
    listingsDebounceRef.current = window.setTimeout(() => {
      listingsDebounceRef.current = null
      lastListingsRefreshAtRef.current = Date.now()
      void loadListings({ throughPage: Math.max(loadedListingsPageRef.current, 1) })
    }, delay)
  }, [loadListings])

  useEffect(
    () => () => {
      if (debounceRef.current !== null) window.clearTimeout(debounceRef.current)
      if (listingsDebounceRef.current !== null) {
        window.clearTimeout(listingsDebounceRef.current)
      }
    },
    [],
  )

  // Stream deltas and gaps only trigger debounced REST refetches of the
  // authoritative lists; nothing is applied from partial stream payloads.
  const stream = useMarketStream({
    onGap: scheduleRefresh,
    onQuotesChanged: scheduleListingsRefresh,
  })
  const firstRender = useRef(true)
  useEffect(() => {
    if (firstRender.current) {
      firstRender.current = false
      return
    }
    scheduleRefresh()
  }, [stream.books, stream.decisions, stream.paper, stream.resolutions, scheduleRefresh])

  const loadMoreListings = useCallback(() => {
    if (listings.loadingMore || listings.rows.length >= listings.total) return
    void loadListings({ throughPage: loadedListingsPageRef.current + 1, append: true })
  }, [listings.loadingMore, listings.rows.length, listings.total, loadListings])

  return { opportunities, listings, paper, disabled, refetch, loadMoreListings }
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
          <h2 className="font-semibold">市场数据暂时不可用</h2>
          <p className="mt-1 text-sm text-muted-foreground">{userFacingApiError(errorCode, 'market')}</p>
          <p className="mt-1 text-sm text-muted-foreground">其他 Tennix 页面仍可继续使用。</p>
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
    data.opportunities.rows.some((row) => row.stale || row.overlay === 'stale') ||
    filteredListings.some((row) => row.stale || row.overlay === 'stale')

  return (
    <div className="min-h-screen bg-background text-foreground">
      <ProductHeader active="markets" marketsHref="/markets" />

      <main id="content" className="mx-auto flex w-full max-w-7xl flex-col gap-6 px-4 py-6 md:px-6 md:py-8">
        <section className="flex flex-col gap-4 border-b pb-6 md:flex-row md:items-end md:justify-between" aria-labelledby="markets-title">
          <div className="max-w-3xl">
            <div className="flex flex-wrap items-center gap-2">
              <span className="rounded-full border px-2.5 py-1 text-xs text-muted-foreground">仅模拟</span>
            </div>
            <h1 id="markets-title" className="mt-3 text-balance text-3xl font-semibold tracking-[-0.035em] sm:text-4xl">比赛市场</h1>
            <p className="mt-3 max-w-2xl text-pretty text-sm leading-relaxed text-muted-foreground sm:text-base">
              查看市场报价和模型判断。所有记录都仅供模拟，不会触发真实交易。
            </p>
          </div>
          <div className="flex items-start gap-2 rounded-lg bg-muted/30 p-3 text-xs leading-relaxed text-muted-foreground md:max-w-xs">
            <ShieldCheck aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-primary" />
            这里显示市场提供的比赛报价；模型判断可能暂不可用。
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
                <h2 className="font-semibold">市场功能暂不可用</h2>
                <p className="mt-1 max-w-md text-sm leading-relaxed text-muted-foreground">
                  {userFacingApiError('p3_disabled', 'market')}
                </p>
              </div>
            </CardContent>
          </Card>
        ) : (
          <>
            {anyStale ? (
              <div role="status" className="flex items-start gap-2 rounded-xl border border-destructive/25 bg-destructive/8 p-4 text-sm text-destructive">
                <AlertTriangle aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
                部分报价更新较慢。页面展示上次有效价格，并暂停相关比赛判断。
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
                        <h2 id="opportunities-title" className="text-lg font-semibold">值得关注的比赛</h2>
                        <p className="mt-1 text-sm text-muted-foreground">正在进行的比赛优先，其次是即将开始的比赛。</p>
                      </div>
                      <span className="font-mono text-xs text-muted-foreground">{data.opportunities.rows.length} 条</span>
                    </div>
                    {data.opportunities.status === 'error' ? (
                      <div role="status" className="flex items-start gap-2 rounded-xl border border-destructive/25 bg-destructive/8 p-4 text-sm text-destructive">
                        <AlertTriangle aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
                        {userFacingApiError(data.opportunities.errorCode, 'market')} 以下为上次成功获取的数据。
                      </div>
                    ) : null}
                    <div className="grid gap-3">
                      {data.opportunities.rows.map((row) => (
                        <OpportunityRow key={row.id} opportunity={row} />
                      ))}
                    </div>
                    <div className="flex items-start gap-2 rounded-lg bg-muted/25 p-3 text-xs leading-relaxed text-muted-foreground">
                      <ShieldCheck aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-primary" />
                      这些判断仅供参考；查看比赛详情不会进行真实交易。
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
                    <p className="text-sm text-muted-foreground" aria-live="polite">
                      已加载 {data.listings.rows.length} / {data.listings.total} 场
                    </p>
                    {data.listings.status === 'error' && data.listings.rows.length === 0 ? (
                      <ErrorCard errorCode={data.listings.errorCode} onRetry={() => void data.refetch()} />
                    ) : filteredListings.length === 0 ? (
                      <Card>
                        <CardContent className="flex min-h-64 flex-col items-center justify-center gap-3 text-center">
                          <div>
                            <h3 className="font-semibold">{hasFilters ? '没有符合条件的比赛' : '目前没有可显示的比赛报价'}</h3>
                            <p className="mt-1 max-w-md text-sm leading-relaxed text-muted-foreground">
                              {hasFilters
                                ? '移除部分筛选条件，或重置筛选后再试。'
                                : '暂时没有比赛报价，请稍后再来查看。'}
                            </p>
                          </div>
                          {hasFilters ? <Button variant="outline" onClick={resetFilters}>重置筛选</Button> : null}
                          {data.listings.rows.length < data.listings.total ? (
                            <Button
                              variant="outline"
                              onClick={data.loadMoreListings}
                              disabled={data.listings.loadingMore}
                            >
                              {data.listings.loadingMore ? '加载中…' : '加载更多'}
                            </Button>
                          ) : null}
                        </CardContent>
                      </Card>
                    ) : (
                      <>
                        {data.listings.status === 'error' ? (
                          <div role="status" className="flex items-start gap-2 rounded-xl border border-destructive/25 bg-destructive/8 p-4 text-sm text-destructive">
                            <AlertTriangle aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
                            {userFacingApiError(data.listings.errorCode, 'market')} 以下为上次成功获取的数据。
                          </div>
                        ) : null}
                        <div className="grid gap-3" aria-live="polite">
                          {filteredListings.map((row) => (
                            <MarketRow key={row.id} market={row} />
                          ))}
                        </div>
                        {data.listings.rows.length < data.listings.total ? (
                          <div className="flex justify-center">
                            <Button
                              variant="outline"
                              onClick={data.loadMoreListings}
                              disabled={data.listings.loadingMore}
                            >
                              {data.listings.loadingMore ? '加载中…' : '加载更多'}
                            </Button>
                          </div>
                        ) : null}
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
                      <h2 className="font-semibold">暂无模拟记录</h2>
                      <p className="mt-1 max-w-md text-sm leading-relaxed text-muted-foreground">
                        符合条件的模拟记录会显示在这里；不涉及真实资金。
                      </p>
                    </div>
                  </CardContent>
                </Card>
              ) : (
                <section className="flex flex-col gap-3" aria-labelledby="paper-ledger-title">
                  <div className="flex items-end justify-between gap-3">
                    <div>
                      <h2 id="paper-ledger-title" className="text-lg font-semibold">模拟记录</h2>
                      <p className="mt-1 text-sm text-muted-foreground">记录模拟投入、当前价值和盈亏变化。</p>
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
                    这些结果来自模拟，不代表真实收益。
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
          <span>仅供参考与模拟，不涉及真实资金</span>
        </div>
      </footer>
    </div>
  )
}
