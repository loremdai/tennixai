'use client'

import { useCallback, useEffect, useRef, useState, useTransition } from 'react'
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
import { getMatches } from '@/lib/api/client'
import type { MatchDto } from '@/lib/api/types'
import { toHomeMatch, toMatchViewModel } from '@/lib/view-models'

const phases = Object.keys(phaseLabels) as ProductPhase[]

type HomePageProps = {
  initialQuestion?: string
}

export function HomePage({ initialQuestion }: HomePageProps) {
  const [phase, setPhase] = useState<ProductPhase>('p1')
  const [prompt, setPrompt] = useState('')
  const [isPending, startTransition] = useTransition()

  const chat = useChatStream('global')
  const busy = chat.state.phase === 'loading' || chat.state.phase === 'streaming'

  const [slate, setSlate] = useState<{ live: MatchDto[]; upcoming: MatchDto[] }>({
    live: [],
    upcoming: [],
  })
  const [slateState, setSlateState] = useState<SlateState>('loading')
  const [slateErrorCode, setSlateErrorCode] = useState<string | null>(null)

  const loadSlate = useCallback(async () => {
    setSlateState('loading')
    try {
      const [live, upcoming] = await Promise.all([getMatches('live'), getMatches('upcoming')])
      setSlate({ live, upcoming })
      setSlateErrorCode(null)
      setSlateState('success')
    } catch (error) {
      const code =
        typeof error === 'object' && error !== null && 'code' in error
          ? String((error as { code: unknown }).code)
          : 'internal_error'
      setSlateErrorCode(code)
      setSlateState('error')
    }
  }, [])

  useEffect(() => {
    void loadSlate()
  }, [loadSlate])

  const initialSentRef = useRef(false)
  useEffect(() => {
    if (!initialQuestion || initialSentRef.current) return
    initialSentRef.current = true
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

  const featuredDto = slate.live[0] ?? slate.upcoming[0] ?? null
  const featured = featuredDto ? toMatchViewModel(featuredDto) : null
  const liveCards = slate.live.map(toHomeMatch)
  const upcomingCards = slate.upcoming.map(toHomeMatch)

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
            {slateState === 'error' && slateErrorCode ? (
              <SlateErrorPanel code={slateErrorCode} onRetry={() => void loadSlate()} />
            ) : (
              <>
                <FeaturedMatchSection phase={phase} match={featured} state={slateState} onAsk={focusAssistant} />
                <LiveNowSection matches={liveCards} state={slateState} onRefresh={() => void loadSlate()} />
                <UpcomingSection matches={upcomingCards} state={slateState} />
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
