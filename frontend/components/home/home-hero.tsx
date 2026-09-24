'use client'

import type { FormEvent, KeyboardEvent } from 'react'
import Image from 'next/image'
import { ArrowRight, Sparkles } from 'lucide-react'

import { homeExampleQueries } from '@/components/home/home-data'
import { Button } from '@/components/ui/button'
import {
  InputGroup,
  InputGroupAddon,
  InputGroupButton,
  InputGroupInput,
} from '@/components/ui/input-group'

type HomeHeroProps = {
  showSearch: boolean
  prompt: string
  onPromptChange: (value: string) => void
  onSubmit: (value: string) => void
  onPromptSelect: (value: string) => void
}

export function HomeHero({
  showSearch,
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
      className="home-reveal relative min-h-[20rem] overflow-hidden rounded-2xl border bg-card"
      aria-labelledby="home-hero-title"
    >
      <Image
        src="/images/tennix-hero.png"
        alt="室内硬地球场上正在正手击球的网球运动员"
        fill
        priority
        sizes="(max-width: 768px) 100vw, 50vw"
        className="object-cover object-[70%_48%] opacity-55"
      />
      <div className="absolute inset-0 bg-[linear-gradient(90deg,var(--card)_0%,color-mix(in_oklab,var(--card)_96%,transparent)_45%,color-mix(in_oklab,var(--card)_58%,transparent)_76%,color-mix(in_oklab,var(--background)_24%,transparent)_100%)]" aria-hidden="true" />
      <div className="absolute inset-0 bg-[linear-gradient(0deg,var(--card)_0%,transparent_46%)] opacity-75" aria-hidden="true" />

      <div className="relative flex min-h-[20rem] max-w-3xl flex-col justify-center gap-5 p-6 sm:p-8 lg:p-10">
        <div className="flex flex-col gap-3">
          <p className="font-mono text-xs font-semibold tracking-[0.16em] text-primary">
            网球 · 赛程 · 数据
          </p>
          <div className="flex flex-col gap-3">
            <h1
              id="home-hero-title"
              className="max-w-2xl text-balance text-4xl font-semibold tracking-[-0.045em] sm:text-5xl lg:text-6xl"
            >
              看比赛，也看懂比赛
            </h1>
            <p className="max-w-xl text-pretty text-base leading-relaxed text-muted-foreground sm:text-lg">
              查赛程、看比分，了解球员与比赛正在发生什么。
            </p>
          </div>
        </div>

        {showSearch ? (
          <div className="flex max-w-2xl flex-col gap-3">
            <form onSubmit={submitPrompt}>
              <label htmlFor="hero-question" className="sr-only">
                向 Tennix 提问
              </label>
              <InputGroup className="h-14 rounded-xl bg-background/90 shadow-2xl backdrop-blur-xl">
                <InputGroupInput
                  id="hero-question"
                  name="hero-question"
                  value={prompt}
                  onChange={(event) => onPromptChange(event.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder="例如：今晚 Sinner 几点比赛？"
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

            <div className="flex flex-wrap gap-2" aria-label="试试这样问">
              {homeExampleQueries.slice(0, 3).map((item) => (
                <Button
                  key={item}
                  variant="outline"
                  size="sm"
                  className="bg-background/65 backdrop-blur-md"
                  onClick={() => onPromptSelect(item)}
                >
                  {item}
                </Button>
              ))}
            </div>
          </div>
        ) : null}

      </div>
    </section>
  )
}
