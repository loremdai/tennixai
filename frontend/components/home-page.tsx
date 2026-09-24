'use client'

import { useCallback, useEffect, useState } from 'react'

import { HomeAssistant } from '@/components/home/home-assistant'
import { HomeHero } from '@/components/home/home-hero'
import { LiveMarketPulse } from '@/components/home/live-market-pulse'
import { MarketPulse } from '@/components/home/market-pulse'
import {
  FeaturedMatchSection,
  LiveNowSection,
  SlateErrorPanel,
  UpcomingSection,
  type SlateState,
} from '@/components/home/home-match-sections'
import { MatchFiltersBar } from '@/components/home/match-filters'
import { ProductHeader } from '@/components/match/match-header'
import type { HomePulseState } from '@/components/p3/p3-preview-data'
import { useChatStream } from '@/hooks/use-chat-stream'
import { getMatchCatalog } from '@/lib/api/client'
import type { FacetCountsDto, MatchCatalogDto, MatchFiltersDto } from '@/lib/api/types'
import { DEFAULT_MATCH_FILTERS } from '@/lib/match-filters'
import { toHomeMatch, toMatchViewModel } from '@/lib/view-models'

type HomePageProps = {
  initialQuestion?: string
  previewP3?: boolean
  initialPulseState?: HomePulseState
  /** Server-probed P3 availability. When false the production Home makes
   * zero P3 requests and renders exactly the pre-P3 layout. */
  p3Enabled?: boolean
}

type SlateStatuses = {
  live: SlateState
  upcoming: SlateState
}

type SlateErrorCodes = {
  live: string | null
  upcoming: string | null
}

function getErrorCode(error: unknown): string {
  return typeof error === 'object' && error !== null && 'code' in error
    ? String((error as { code: unknown }).code)
    : 'internal_error'
}

function mergeFacetCounts(
  live: FacetCountsDto | null,
  upcoming: FacetCountsDto | null,
): FacetCountsDto | null {
  if (!live && !upcoming) return null
  const base = live ?? upcoming
  const other = live && upcoming ? upcoming : null
  if (!other || !base) return base
  const sumGroup = <K extends string>(a: Record<K, number>, b: Record<K, number>) => {
    const keys = new Set([...Object.keys(a), ...Object.keys(b)]) as Set<K>
    const merged = {} as Record<K, number>
    for (const key of keys) merged[key] = (a[key] ?? 0) + (b[key] ?? 0)
    return merged
  }
  return {
    circuits: sumGroup(base.circuits, other.circuits),
    genders: sumGroup(base.genders, other.genders),
    disciplines: sumGroup(base.disciplines, other.disciplines),
  }
}

function hasLiveMatchesOutsideFilters(
  catalog: MatchCatalogDto | null,
  filters: MatchFiltersDto,
): boolean {
  if (!catalog || catalog.matches.length > 0) return false

  const hasOutsideValue = <T extends string>(
    selected: readonly T[],
    counts: Record<T, number>,
  ) =>
    selected.length > 0 &&
    (Object.entries(counts) as Array<[string, number]>).some(
      ([value, count]) => count > 0 && !selected.includes(value as T),
    )

  return (
    hasOutsideValue(filters.circuits, catalog.facet_counts.circuits) ||
    hasOutsideValue(filters.genders, catalog.facet_counts.genders) ||
    hasOutsideValue(filters.disciplines, catalog.facet_counts.disciplines)
  )
}

export function HomePage({
  initialQuestion,
  previewP3 = false,
  initialPulseState = 'populated',
  p3Enabled = false,
}: HomePageProps) {
  const [prompt, setPrompt] = useState('')
  const previewEnabled = previewP3
  const showP3Preview = previewEnabled

  const chat = useChatStream('global')
  const busy = chat.state.phase === 'loading' || chat.state.phase === 'streaming'

  const [filters, setFilters] = useState<MatchFiltersDto>(DEFAULT_MATCH_FILTERS)
  const [catalogs, setCatalogs] = useState<{
    live: MatchCatalogDto | null
    upcoming: MatchCatalogDto | null
  }>({
    live: null,
    upcoming: null,
  })
  const [slateState, setSlateState] = useState<SlateStatuses>({
    live: previewP3 ? 'success' : 'loading',
    upcoming: previewP3 ? 'success' : 'loading',
  })
  const [slateErrorCodes, setSlateErrorCodes] = useState<SlateErrorCodes>({
    live: null,
    upcoming: null,
  })

  const loadSlate = useCallback(async () => {
    if (previewEnabled) {
      setCatalogs({ live: null, upcoming: null })
      setSlateState({ live: 'success', upcoming: 'success' })
      setSlateErrorCodes({ live: null, upcoming: null })
      return
    }

    setSlateState({ live: 'loading', upcoming: 'loading' })
    setSlateErrorCodes({ live: null, upcoming: null })

    const [liveResult, upcomingResult] = await Promise.allSettled([
      getMatchCatalog('live', filters),
      getMatchCatalog('upcoming', filters),
    ])

    setCatalogs({
      live: liveResult.status === 'fulfilled' ? liveResult.value : null,
      upcoming: upcomingResult.status === 'fulfilled' ? upcomingResult.value : null,
    })
    setSlateState({
      live: liveResult.status === 'fulfilled' ? 'success' : 'error',
      upcoming: upcomingResult.status === 'fulfilled' ? 'success' : 'error',
    })
    setSlateErrorCodes({
      live: liveResult.status === 'rejected' ? getErrorCode(liveResult.reason) : null,
      upcoming: upcomingResult.status === 'rejected' ? getErrorCode(upcomingResult.reason) : null,
    })
  }, [filters, previewEnabled])

  useEffect(() => {
    void loadSlate()
  }, [loadSlate])

  useEffect(() => {
    if (!initialQuestion || previewEnabled) return
    // StrictMode remounts abort the first send; re-sending on remount keeps the
    // initial question working while production still sends exactly once.
    void chat.send(initialQuestion)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const showAnswer = useCallback(
    (question: string, scroll = true) => {
      const value = question.trim()
      if (!value || busy) return
      if (!previewEnabled) void chat.send(value)
      setPrompt('')
      if (scroll) {
        window.requestAnimationFrame(() => {
          document.getElementById('assistant')?.scrollIntoView({ behavior: 'smooth', block: 'center' })
        })
      }
    },
    [busy, chat, previewEnabled],
  )

  function focusAssistant() {
    document.getElementById('assistant')?.scrollIntoView({ behavior: 'smooth', block: 'center' })
    window.setTimeout(() => document.getElementById('home-question')?.focus(), 350)
  }

  const liveMatches = catalogs.live?.matches ?? []
  const upcomingMatches = catalogs.upcoming?.matches ?? []
  const featuredId =
    catalogs.live?.featured_match_id ?? catalogs.upcoming?.featured_match_id ?? null
  const featuredDto = featuredId
    ? (liveMatches.find((match) => match.id === featuredId) ??
      upcomingMatches.find((match) => match.id === featuredId) ??
      null)
    : null
  const featured = featuredDto ? toMatchViewModel(featuredDto) : null
  const liveCards = liveMatches.map(toHomeMatch)
  const upcomingCards = upcomingMatches.map(toHomeMatch)
  const facetCounts = mergeFacetCounts(
    catalogs.live?.facet_counts ?? null,
    catalogs.upcoming?.facet_counts ?? null,
  )
  const liveHasMatchesOutsideFilters = hasLiveMatchesOutsideFilters(catalogs.live, filters)
  const allSlateFailed = slateState.live === 'error' && slateState.upcoming === 'error'
  const featuredState: SlateState =
    featuredDto || slateState.live === 'success' || slateState.upcoming === 'success'
      ? 'success'
      : 'loading'

  return (
    <div className="min-h-screen bg-background text-foreground">
      <a
        href="#main-content"
        className="sr-only fixed left-3 top-3 z-50 rounded-lg bg-primary px-3 py-2 text-sm font-medium text-primary-foreground focus:not-sr-only"
      >
        跳至主要内容
      </a>
      <ProductHeader active="home" marketsHref={showP3Preview ? '/markets?preview=p3' : '/markets'} />

      <main
        id="main-content"
        tabIndex={-1}
        className="mx-auto flex max-w-7xl scroll-mt-20 flex-col gap-4 px-4 py-5 md:px-6 md:py-7"
      >
        <HomeHero
          showSearch={!busy && chat.state.phase === 'idle' && !previewEnabled}
          prompt={prompt}
          onPromptChange={setPrompt}
          onSubmit={showAnswer}
          onPromptSelect={showAnswer}
        />

        {chat.state.phase !== 'idle' ? (
          <HomeAssistant
            prompt={prompt}
            chat={chat.state}
            busy={busy}
            onPromptChange={setPrompt}
            onSubmit={showAnswer}
          />
        ) : null}

        <div className="home-reveal flex min-w-0 flex-col gap-6">
          <div className="flex min-w-0 flex-col gap-6">
            {allSlateFailed ? (
              <SlateErrorPanel
                code={slateErrorCodes.live ?? slateErrorCodes.upcoming ?? 'internal_error'}
                onRetry={() => void loadSlate()}
              />
            ) : (
              <>
                <MatchFiltersBar
                  filters={filters}
                  facetCounts={facetCounts}
                  onChange={setFilters}
                  onReset={() => setFilters(DEFAULT_MATCH_FILTERS)}
                />
                <FeaturedMatchSection match={featured} state={featuredState} onAsk={focusAssistant} />
                <LiveNowSection
                  matches={liveCards}
                  state={slateState.live}
                  errorCode={slateErrorCodes.live}
                  onRefresh={() => void loadSlate()}
                  hasMatchesOutsideFilters={liveHasMatchesOutsideFilters}
                  onShowAllMatches={() =>
                    setFilters({ circuits: [], genders: [], disciplines: [] })
                  }
                />
                <UpcomingSection
                  matches={upcomingCards}
                  state={slateState.upcoming}
                  errorCode={slateErrorCodes.upcoming}
                  onRefresh={() => void loadSlate()}
                />
              </>
            )}
          </div>
        </div>

        {showP3Preview ? (
          <MarketPulse initialState={initialPulseState} />
        ) : p3Enabled ? (
          <LiveMarketPulse />
        ) : null}
      </main>

      <footer className="border-t">
        <div className="mx-auto flex max-w-7xl flex-col justify-between gap-2 px-4 py-6 text-sm text-muted-foreground sm:flex-row md:px-6">
          <span>Tennix · 网球赛况与数据</span>
          <span>{showP3Preview ? '示例内容，不代表实时行情' : '比赛时间均为北京时间'}</span>
        </div>
      </footer>
    </div>
  )
}
