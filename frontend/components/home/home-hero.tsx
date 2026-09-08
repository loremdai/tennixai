'use client'

import type { FormEvent, KeyboardEvent } from 'react'
import Image from 'next/image'
import Link from 'next/link'
import type { LucideIcon } from 'lucide-react'
import {
  ArrowRight,
  CalendarDays,
  FileClock,
  Radio,
  Search,
  Send,
  Sparkles,
  Star,
  TrendingUp,
} from 'lucide-react'

import { homeExampleQueries } from '@/components/home/home-data'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import {
  InputGroup,
  InputGroupAddon,
  InputGroupButton,
  InputGroupInput,
} from '@/components/ui/input-group'
import type { ProductPhase } from '@/components/match/match-data'

type HomeHeroProps = {
  phase: ProductPhase
  prompt: string
  onPromptChange: (value: string) => void
  onSubmit: (value: string) => void
  onPromptSelect: (value: string) => void
}

export function HomeHero({
  phase,
  prompt,
  onPromptChange,
  onSubmit,
  onPromptSelect,
}: HomeHeroProps) {
  function submitPrompt(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const value = prompt.trim()
    if (!value) return
    onSubmit(value)
  }

  function handleKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === 'Enter' && (event.nativeEvent.isComposing || event.keyCode === 229)) {
      event.preventDefault()
    }
  }

  return (
    <section
      data-tone="hero"
      className="home-reveal relative min-h-[25rem] overflow-hidden rounded-2xl border bg-card"
      aria-labelledby="home-hero-title"
    >
      <Image
        src="/images/tennix-hero.png"
        alt="室内硬地球场上正在正手击球的网球运动员"
        fill
        priority
        sizes="(max-width: 768px) 100vw, 50vw"
        className="object-cover object-[70%_48%] opacity-70"
      />
      <div className="absolute inset-0 bg-[linear-gradient(90deg,var(--card)_0%,color-mix(in_oklab,var(--card)_96%,transparent)_44%,color-mix(in_oklab,var(--card)_52%,transparent)_72%,color-mix(in_oklab,var(--background)_28%,transparent)_100%)]" aria-hidden="true" />
      <div className="absolute inset-0 bg-[linear-gradient(0deg,var(--card)_0%,transparent_42%)] opacity-70" aria-hidden="true" />

      <div className="relative flex min-h-[25rem] max-w-3xl flex-col justify-center gap-6 p-6 sm:p-9 lg:p-12">
        <div className="flex flex-col gap-4">
          <p className="font-mono text-xs font-semibold tracking-[0.2em] text-primary">
            TENNIS. DATA. INTELLIGENCE.
          </p>
          <div className="flex flex-col gap-3">
            <h1
              id="home-hero-title"
              className="max-w-2xl text-balance text-4xl font-semibold tracking-[-0.045em] sm:text-5xl lg:text-6xl"
            >
              Your AI Tennis Companion
            </h1>
            <p className="text-pretty text-base leading-relaxed text-muted-foreground sm:text-lg">
              Real-time data. Deeper insights. Smarter decisions.
            </p>
          </div>
        </div>

        <div className="flex max-w-2xl flex-col gap-3">
          <form onSubmit={submitPrompt}>
            <label htmlFor="hero-question" className="sr-only">
              向 Tennix 询问网球问题
            </label>
            <InputGroup className="h-14 rounded-xl bg-background/80 shadow-2xl backdrop-blur-xl">
              <InputGroupInput
                id="hero-question"
                name="hero-question"
                value={prompt}
                onChange={(event) => onPromptChange(event.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="询问任何网球问题…"
                autoComplete="off"
                className="text-base"
              />
              <InputGroupAddon align="inline-start">
                <Sparkles aria-hidden="true" />
              </InputGroupAddon>
              <InputGroupAddon align="inline-end">
                <InputGroupButton type="submit" variant="default" size="icon-sm" aria-label="发送问题">
                  <ArrowRight aria-hidden="true" />
                </InputGroupButton>
              </InputGroupAddon>
            </InputGroup>
          </form>

          <div className="flex flex-wrap gap-2" aria-label="示例问题">
            {homeExampleQueries.map((item) => (
              <Button
                key={item}
                variant="outline"
                size="sm"
                className="bg-background/55 backdrop-blur-md"
                onClick={() => onPromptSelect(item)}
              >
                {item}
              </Button>
            ))}
          </div>
        </div>

        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <span className="size-1.5 rounded-full bg-primary" aria-hidden="true" />
          <span>{phase === 'p1' ? '信息助手在线' : phase === 'p2' ? '实时数据已连接' : '决策预览已连接'}</span>
        </div>
      </div>

      <blockquote className="absolute bottom-8 right-8 hidden max-w-52 border-l-2 border-primary pl-4 text-sm leading-relaxed text-foreground lg:block">
        “Better data.<br />A deeper game.”
      </blockquote>
    </section>
  )
}

type QuickAction = {
  label: string
  detail: string
  href: string
  icon: LucideIcon
  live?: boolean
  beta?: boolean
}

const quickActions: QuickAction[] = [
  { label: 'Live Now', detail: '正在直播', href: '#live', icon: Radio, live: true },
  { label: 'Tonight’s Matches', detail: '今晚赛程', href: '#upcoming', icon: CalendarDays },
  { label: 'Followed Players', detail: '后续阶段接入', href: '#players', icon: Star },
  { label: 'Player Search', detail: '查找任意球员', href: '#assistant', icon: Search },
  { label: 'Recent Results', detail: 'P1 暂不支持', href: '#results', icon: FileClock },
  { label: 'Market Watch', detail: '追踪机会', href: '#markets', icon: TrendingUp, beta: true },
]

export function HomeQuickActions() {
  return (
    <nav className="home-reveal grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6" aria-label="快捷入口">
      {quickActions.map(({ label, detail, href, icon: Icon, live, beta }) => (
        <Link
          key={label}
          href={href}
          className="group rounded-xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <Card size="sm" className="h-full min-h-24 transition-transform group-hover:-translate-y-0.5 group-hover:ring-primary/35">
            <CardContent className="flex h-full flex-col justify-between gap-4">
              <div className="flex items-start justify-between gap-2">
                <span className={live ? 'text-live' : 'text-primary'}>
                  <Icon aria-hidden="true" className="size-4" />
                </span>
                {beta ? <Badge data-tone="beta" variant="outline">BETA</Badge> : null}
                {live ? <span className="live-pulse mt-1 size-1.5 rounded-full bg-live" aria-hidden="true" /> : null}
              </div>
              <div>
                <p className="truncate text-sm font-semibold">{label}</p>
                <p className="mt-1 text-xs text-muted-foreground">{detail}</p>
              </div>
            </CardContent>
          </Card>
        </Link>
      ))}
    </nav>
  )
}
