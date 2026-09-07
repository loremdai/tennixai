'use client'

import { useState, useTransition } from 'react'
import { Layers3 } from 'lucide-react'

import { HomeAssistant } from '@/components/home/home-assistant'
import {
  answerHomeQuestion,
  type HomeAnswer,
} from '@/components/home/home-data'
import { HomeHero, HomeQuickActions } from '@/components/home/home-hero'
import { MarketIntelligenceCard } from '@/components/home/home-intelligence'
import {
  FeaturedMatchSection,
  LiveNowSection,
  UpcomingSection,
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

const phases = Object.keys(phaseLabels) as ProductPhase[]

type HomePageProps = {
  initialQuestion?: string
}

export function HomePage({ initialQuestion }: HomePageProps) {
  const [phase, setPhase] = useState<ProductPhase>('p1')
  const [prompt, setPrompt] = useState('')
  const [answer, setAnswer] = useState<HomeAnswer | null>(() =>
    initialQuestion ? answerHomeQuestion(initialQuestion) : null,
  )
  const [isPending, startTransition] = useTransition()

  function showAnswer(question: string, scroll = true) {
    const value = question.trim()
    if (!value) return
    setAnswer(answerHomeQuestion(value))
    setPrompt('')
    if (scroll) {
      window.requestAnimationFrame(() => {
        document.getElementById('assistant')?.scrollIntoView({ behavior: 'smooth', block: 'center' })
      })
    }
  }

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
              answer={answer}
              onPromptChange={setPrompt}
              onSubmit={showAnswer}
              onPromptSelect={showAnswer}
            />
            <RecentResultsCard />
            <MarketIntelligenceCard phase={phase} />
          </aside>

          <div className="flex min-w-0 flex-col gap-6 lg:col-start-1 lg:row-start-1">
            <FeaturedMatchSection phase={phase} onAsk={focusAssistant} />
            <LiveNowSection />
            <UpcomingSection />
            <FollowedPlayersSection />
          </div>
        </div>
      </main>

      <footer className="border-t">
        <div className="mx-auto flex max-w-7xl flex-col justify-between gap-2 px-4 py-6 text-sm text-muted-foreground sm:flex-row md:px-6">
          <span>Tennix · Tennis, data, intelligence.</span>
          <span>样例数据仅用于产品界面演示</span>
        </div>
      </footer>
    </div>
  )
}
