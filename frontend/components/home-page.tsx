'use client'

import { useCallback, useEffect, useState, useTransition } from 'react'
import { Layers3 } from 'lucide-react'

import { HomeAssistant } from '@/components/home/home-assistant'
import { HomeHero, HomeQuickActions } from '@/components/home/home-hero'
import { MarketIntelligenceCard } from '@/components/home/home-intelligence'
import {
  FeaturedMatchSection,
  LiveNowSection,
  SlateErrorPanel,
  UpcomingSection,
  type SlateState,
} from '@/components/home/home-match-sections'
import { MatchFiltersBar } from '@/components/home/match-filters'
import {
  FollowedPlayersSection,
  RecentResultsCard,
} from '@/components/home/home-player-sections'
import {
  phaseLabels,
  type ProductPhase,
} from '@/components/match/match-data'
import { ProductHeader } from '@/components/match/match-header'
import { Badge } from '@/components/ui/badge'
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group'
import { useChatStream } from '@/hooks/use-chat-stream'
import { getMatchCatalog } from '@/lib/api/client'
import type { FacetCountsDto, MatchCatalogDto, MatchFiltersDto } from '@/lib/api/types'
import { DEFAULT_MATCH_FILTERS } from '@/lib/match-filters'
import { toHomeMatch, toMatchViewModel } from '@/lib/view-models'

const phases = Object.keys(phaseLabels) as ProductPhase[]

type HomePageProps = {
  initialQuestion?: string
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

export function HomePage({ initialQuestion }: HomePageProps) {
  const [phase, setPhase] = useState<ProductPhase>('p1')
  const [prompt, setPrompt] = useState('')
  const [isPending, startTransition] = useTransition()

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
    live: 'loading',
    upcoming: 'loading',
  })
  const [slateErrorCodes, setSlateErrorCodes] = useState<SlateErrorCodes>({
    live: null,
    upcoming: null,
  })

  const loadSlate = useCallback(async () => {
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
  }, [filters])

  useEffect(() => {
    void loadSlate()
  }, [loadSlate])

  useEffect(() => {
    if (!initialQuestion) return
    // StrictMode remounts abort the first send; re-sending on remount keeps the
    // initial question working while production still sends exactly once.
    void chat.send(initialQuestion)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const showAnswer = useCallback(
    (question: string, scroll = true) => {
      const value = question.trim()
      if (!value || busy) return
      void chat.send(value)
      setPrompt('')
      if (scroll) {
        window.requestAnimationFrame(() => {
          document.getElementById('assistant')?.scrollIntoView({ behavior: 'smooth', block: 'center' })
        })
      }
    },
    [busy, chat],
  )

  function handlePhaseChange(values: string[]) {
    const nextPhase = values.at(-1) as ProductPhase | undefined
    if (!nextPhase || nextPhase === phase) return

    startTransition(() => {
      setPhase(nextPhase)
      setPrompt('')
    })
  }

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
      <ProductHeader active="home" />

      <main
        id="main-content"
        tabIndex={-1}
        className="mx-auto flex max-w-7xl scroll-mt-20 flex-col gap-4 px-4 py-5 md:px-6 md:py-7"
      >
        <section
          id="phase"
          className="home-reveal flex scroll-mt-24 flex-col justify-between gap-3 rounded-xl border bg-card/65 p-3 sm:flex-row sm:items-center"
          aria-labelledby="phase-title"
        >
          <div className="flex items-center gap-3">
            <div className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-secondary text-primary">
              <Layers3 aria-hidden="true" className="size-4" />
            </div>
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <p id="phase-title" className="text-sm font-semibold">产品演进预览</p>
                <Badge variant="outline">稳定信息架构</Badge>
              </div>
              <p className="mt-1 text-sm text-muted-foreground">
                {phaseLabels[phase].title} · {phaseLabels[phase].description}
              </p>
            </div>
          </div>

          <ToggleGroup
            value={[phase]}
            onValueChange={handlePhaseChange}
            variant="outline"
            spacing={1}
            aria-label="选择产品阶段"
            aria-busy={isPending}
            className="phase-switch w-full sm:w-fit"
          >
            {phases.map((item) => (
              <ToggleGroupItem
                key={item}
                value={item}
                className="flex-1 sm:flex-none"
                aria-label={phaseLabels[item].title}
              >
                {phaseLabels[item].short}
              </ToggleGroupItem>
            ))}
          </ToggleGroup>
        </section>

        <HomeHero
          phase={phase}
          prompt={prompt}
          onPromptChange={setPrompt}
          onSubmit={showAnswer}
          onPromptSelect={showAnswer}
        />

        <HomeQuickActions />

        <div className="home-reveal grid items-start gap-4 lg:grid-cols-[minmax(0,1fr)_22rem]">
          <aside className="flex min-w-0 flex-col gap-4 lg:col-start-2 lg:row-start-1" aria-label="Tennix 智能侧栏">
            <HomeAssistant
              prompt={prompt}
              chat={chat.state}
              busy={busy}
              onPromptChange={setPrompt}
              onSubmit={showAnswer}
              onPromptSelect={showAnswer}
            />
            <RecentResultsCard />
            <MarketIntelligenceCard phase={phase} />
          </aside>

          <div className="flex min-w-0 flex-col gap-6 lg:col-start-1 lg:row-start-1">
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
                <FeaturedMatchSection phase={phase} match={featured} state={featuredState} onAsk={focusAssistant} />
                <LiveNowSection
                  matches={liveCards}
                  state={slateState.live}
                  errorCode={slateErrorCodes.live}
                  onRefresh={() => void loadSlate()}
                />
                <UpcomingSection
                  matches={upcomingCards}
                  state={slateState.upcoming}
                  errorCode={slateErrorCodes.upcoming}
                  onRefresh={() => void loadSlate()}
                />
              </>
            )}
            <FollowedPlayersSection />
          </div>
        </div>
      </main>

      <footer className="border-t">
        <div className="mx-auto flex max-w-7xl flex-col justify-between gap-2 px-4 py-6 text-sm text-muted-foreground sm:flex-row md:px-6">
          <span>Tennix · Tennis, data, intelligence.</span>
          <span>数据由 Tennix 服务提供 · 时间为澳门本地时间</span>
        </div>
      </footer>
    </div>
  )
}
