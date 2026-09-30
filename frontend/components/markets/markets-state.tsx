'use client'

// Production /markets workspace with three read-only P3 views, canonical
// filters, internal navigation, and explicit loading/error/quote states.
// Never imports preview fixtures or calculates probability, fills, or settlement.

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
import type { MarketListParams } from '@/lib/api/client'
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
const DEFAULT_TIERS: CircuitTier[] = ['atp', 'wta']
const TIER_ORDER: CircuitTier[] = ['atp', 'wta', 'challenger', 'itf', 'other']

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

export function useMarketsWorkspace({
  tiers,
  gender,
  phase,
}: {
  tiers: CircuitTier[]
  gender: GenderFilter
  phase: PhaseFilter
}): MarketsWorkspaceData {
  const filterKey = `${tiers.join(',')}|${gender}|${phase}`
  const activeFilterKeyRef = useRef(filterKey)
  activeFilterKeyRef.current = filterKey
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
  const listingsRequestIdRef = useRef(0)
  const loadedFilterKeyRef = useRef<string | null>(null)
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
    const requestId = ++listingsRequestIdRef.current
    const requestFilterKey = filterKey
    if (!append) {
      const sameFilter = loadedFilterKeyRef.current === requestFilterKey
      setListings((current) => ({
        status: sameFilter && current.rows.length > 0 ? 'ready' : 'loading',
        errorCode: null,
        rows: sameFilter ? current.rows : [],
        page: sameFilter ? current.page : 0,
        total: sameFilter ? current.total : 0,
        loadingMore: false,
      }))
    }
    if (append) {
      setListings((current) => ({ ...current, loadingMore: true, errorCode: null }))
    }
    try {
      const firstPage = append ? throughPage : 1
      const pages = []
      const filters: Omit<MarketListParams, 'page' | 'pageSize'> = {
        ...(tiers.length > 0 ? { tier: tiers } : {}),
        ...(gender !== 'all' ? { gender } : {}),
        ...(phase !== 'all' ? { phase } : {}),
      }
      for (let page = firstPage; page <= throughPage; page += 1) {
        pages.push(await listMarkets({ ...filters, page, pageSize: PAGE_SIZE }))
      }
      if (
        !mountedRef.current ||
        requestId !== listingsRequestIdRef.current ||
        activeFilterKeyRef.current !== requestFilterKey
      ) return
      const now = new Date()
      const incoming = pages.flatMap((page) => page.markets.map((row) => toMarketRow(row, now)))
      const total = pages[0]?.total ?? 0
      loadedListingsPageRef.current = throughPage
      loadedFilterKeyRef.current = requestFilterKey
      setListings((current) => {
        const combined = append && loadedFilterKeyRef.current === requestFilterKey
          ? [...current.rows, ...incoming]
          : incoming
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
      if (
        !mountedRef.current ||
        requestId !== listingsRequestIdRef.current ||
        activeFilterKeyRef.current !== requestFilterKey
      ) return
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
  }, [filterKey, tiers, gender, phase])

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
    void loadOpportunities()
    void loadPaper()
  }, [loadOpportunities, loadPaper])

  useEffect(() => {
    loadedListingsPageRef.current = 0
    void loadListings({ throughPage: 1 })
  }, [loadListings])

  const refetchRef = useRef(refetch)
  refetchRef.current = refetch
  const loadListingsRef = useRef(loadListings)
  loadListingsRef.current = loadListings

  const scheduleRefresh = useCallback(() => {
    if (debounceRef.current !== null) window.clearTimeout(debounceRef.current)
    debounceRef.current = window.setTimeout(() => {
      debounceRef.current = null
      void refetchRef.current()
    }, REFRESH_DEBOUNCE_MS)
  }, [])

  const scheduleListingsRefresh = useCallback(() => {
    if (listingsDebounceRef.current !== null) return
    const elapsed = Date.now() - lastListingsRefreshAtRef.current
    const delay = Math.max(0, LISTING_QUOTE_REFRESH_INTERVAL_MS - elapsed)
    listingsDebounceRef.current = window.setTimeout(() => {
      listingsDebounceRef.current = null
      lastListingsRefreshAtRef.current = Date.now()
      void loadListingsRef.current({ throughPage: Math.max(loadedListingsPageRef.current, 1) })
    }, delay)
  }, [])

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
  initialTiers = DEFAULT_TIERS,
  initialGender = 'all',
  initialPhase = 'all',
}: {
  initialView?: MarketsTabValue
  initialTiers?: CircuitTier[]
  initialGender?: GenderFilter
  initialPhase?: PhaseFilter
}) {
  const [view, setView] = useState<MarketsTabValue>(initialView)
  const [tiers, setTiers] = useState<CircuitTier[]>(initialTiers)
  const [gender, setGender] = useState<GenderFilter>(initialGender)
  const [phase, setPhase] = useState<PhaseFilter>(initialPhase)
  const data = useMarketsWorkspace({ tiers, gender, phase })

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
    const ordered = TIER_ORDER.filter((tier) => next.includes(tier))
    setTiers(ordered)
    updateUrl((url) => {
      url.searchParams.delete('tier')
      if (ordered.length === 0) url.searchParams.set('tier', 'all')
      else ordered.forEach((tier) => url.searchParams.append('tier', tier))
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
    setTiers(DEFAULT_TIERS)
    setGender('all')
    setPhase('all')
    updateUrl((url) => {
      url.searchParams.delete('tier')
      url.searchParams.delete('gender')
      url.searchParams.delete('phase')
    })
  }

  const hasDefaultTiers =
    tiers.length === DEFAULT_TIERS.length && DEFAULT_TIERS.every((tier) => tiers.includes(tier))
  const hasFilters = !hasDefaultTiers || gender !== 'all' || phase !== 'all'
  const anyStale =
    data.opportunities.rows.some((row) => row.stale || row.overlay === 'stale') ||
    data.listings.rows.some((row) => row.stale || row.overlay === 'stale')

  return (
    <div className="min-h-screen bg-background text-foreground">
      <ProductHeader active="markets" marketsHref="/markets" variant="markets" />

      <main id="content" className="mx-auto flex w-full max-w-7xl flex-col gap-5 px-4 py-6 md:px-6 md:py-8">
        <section className="flex flex-col gap-2" aria-labelledby="markets-title">
          <div className="max-w-3xl">
            <p className="text-sm font-medium text-primary">网球 · 市场 · 报价</p>
            <div className="mt-2 flex flex-wrap items-center gap-3">
              <h1 id="markets-title" className="text-balance text-4xl font-semibold tracking-[-0.035em] sm:text-5xl">比赛市场</h1>
              <span className="rounded-full border border-foreground/15 px-2.5 py-1 text-xs text-muted-foreground">仅模拟</span>
            </div>
            <p className="mt-1 text-pretty text-sm leading-relaxed text-muted-foreground sm:text-base">
              浏览网球比赛的真实报价与数据状态。
            </p>
          </div>
        </section>

        <MarketsTabs
          view={view}
          onSelect={selectView}
          counts={{
            opportunities: data.opportunities.rows.length,
            all: data.listings.total,
            paper: data.paper.open.length + data.paper.recent.length,
          }}
        />

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
              <div role="status" className="flex items-start gap-2 rounded-xl border border-destructive/25 bg-destructive/8 p-3 text-sm text-destructive">
                <AlertTriangle aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
                部分报价更新较慢。页面展示上次有效价格，并暂停相关比赛判断。
              </div>
            ) : null}

            <div
              id={`markets-panel-${view}`}
              role="tabpanel"
              aria-labelledby={`markets-tab-${view}`}
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
                  </section>
                )
              ) : view === 'all' ? (
                <section className="flex flex-col gap-4" aria-label="全部市场">
                  <MarketFilters
                    tiers={tiers}
                    gender={gender}
                    phase={phase}
                    onTiersChange={changeTiers}
                    onGenderChange={changeGender}
                    onPhaseChange={changePhase}
                    onReset={resetFilters}
                    canReset={hasFilters}
                  />
                  <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground" aria-live="polite">
                    <span className="rounded-lg border border-foreground/10 px-3 py-2">
                      已加载 {data.listings.rows.length} / 全部 {data.listings.total} 个市场
                    </span>
                    <span className="rounded-lg border border-foreground/10 px-3 py-2">
                      赛事级别优先 · 进行中 → 赛前 → 已结束
                    </span>
                    <span className="ml-auto inline-flex items-center gap-1.5 px-2 py-2">
                      <span className="size-1.5 rounded-full bg-primary" aria-hidden="true" />
                      报价数据
                    </span>
                  </div>
                  {data.listings.status === 'loading' ? (
                    <LoadingSkeleton />
                  ) : data.listings.status === 'error' && data.listings.rows.length === 0 ? (
                    <ErrorCard errorCode={data.listings.errorCode} onRetry={() => void data.refetch()} />
                  ) : data.listings.rows.length === 0 ? (
                    <Card>
                      <CardContent className="flex flex-col items-start gap-3 p-5 text-left">
                        <div>
                          <h3 className="font-semibold">{hasFilters ? '没有符合条件的市场' : '目前没有可显示的比赛报价'}</h3>
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
                        {data.listings.rows.map((row) => (
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
                </section>
              ) : data.paper.status === 'loading' ? (
                <LoadingSkeleton />
              ) : data.paper.status === 'error' && data.paper.open.length === 0 && data.paper.recent.length === 0 ? (
                <ErrorCard errorCode={data.paper.errorCode} onRetry={() => void data.refetch()} />
              ) : data.paper.open.length === 0 && data.paper.recent.length === 0 ? (
                <Card>
                  <CardContent className="flex flex-col items-start gap-2 p-5 text-left">
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
                  {data.paper.open.length > 0 ? (
                    <section className="flex flex-col gap-3" aria-labelledby="paper-open-title">
                      <div className="flex items-center justify-between gap-2">
                        <h3 id="paper-open-title" className="font-semibold">进行中</h3>
                        <span className="text-xs text-muted-foreground">{data.paper.open.length} 条</span>
                      </div>
                      <div className="grid gap-3">
                        {data.paper.open.map((row) => <PaperRow key={row.id} record={row} />)}
                      </div>
                    </section>
                  ) : null}
                  {data.paper.recent.length > 0 ? (
                    <section className="flex flex-col gap-3" aria-labelledby="paper-recent-title">
                      <div className="flex items-center justify-between gap-2">
                        <h3 id="paper-recent-title" className="font-semibold">近期已结束</h3>
                        <span className="text-xs text-muted-foreground">{data.paper.recent.length} 条</span>
                      </div>
                      <div className="grid gap-3">
                        {data.paper.recent.map((row) => <PaperRow key={row.id} record={row} />)}
                      </div>
                    </section>
                  ) : null}
                </section>
              )}
            </div>
          </>
        )}
      </main>

      <footer className="border-t">
        <div className="mx-auto flex max-w-7xl flex-col justify-between gap-2 px-4 py-5 text-sm text-muted-foreground sm:flex-row md:px-6">
          <span>Tennix · 比赛智能，逐分解释</span>
          <span>仅供参考与模拟，不涉及真实交易</span>
        </div>
      </footer>
    </div>
  )
}
