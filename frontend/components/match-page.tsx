'use client'

import { useState, useTransition } from 'react'
import { Layers3 } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group'

import {
  matchStatusLabels,
  type MatchHighlight,
  type MatchStatus,
} from './match/match-data'
import { ProductHeader } from './match/match-header'
import { MatchHero } from './match/match-hero'
import { MatchMainColumn } from './match/match-main'
import {
  type AssistantAnswer,
  MatchSidebar,
} from './match/match-sidebar'

const statuses = Object.keys(matchStatusLabels) as MatchStatus[]

type MatchPageProps = {
  initialStatus?: MatchStatus
}

function answerQuestion(question: string, status: MatchStatus): AssistantAnswer {
  const normalized = question.trim().toLowerCase()

  if (status === 'upcoming') {
    if (normalized.includes('几点') || normalized.includes('时间') || normalized.includes('start')) {
      return {
        label: '开赛时间',
        question,
        answer: '本场比赛计划于今天 20:30 开始，地点是都灵 Inalpi Arena。若前一场比赛延长，时间会自动更新。',
      }
    }

    if (normalized.includes('赛事') || normalized.includes('tournament')) {
      return {
        label: '赛事信息',
        question,
        answer: '这是 ATP Finals 男单比赛，也是赛季末最重要的室内硬地赛事之一。',
      }
    }

    if (normalized.includes('轮') || normalized.includes('round')) {
      return {
        label: '比赛轮次',
        question,
        answer: '这是男单半决赛，胜者将进入 ATP Finals 决赛。',
      }
    }

    if (normalized.includes('场地') || normalized.includes('surface') || normalized.includes('硬地')) {
      return {
        label: '场地信息',
        question,
        answer: '比赛将在室内硬地进行。具体球场尚未公布，开赛前会自动补全。',
      }
    }

    return {
      label: '赛前上下文',
      question,
      answer: 'Sinner 与 Alcaraz 将于今天 20:30 在都灵进行 ATP Finals 半决赛，赛制为三盘两胜。',
    }
  }

  if (status === 'live') {
    if (
      normalized.includes('发球表现') ||
      normalized.includes('一发') ||
      normalized.includes('serving')
    ) {
      return {
        label: '发球表现',
        question,
        answer: 'Sinner 目前的一发表现更强：一发成功率 68%，一发得分率 79%，并已发出 8 记 ACE。',
        highlight: 'serve-stats',
        metrics: [
          { label: '一发成功率', value: '68%' },
          { label: '一发得分率', value: '79%' },
          { label: 'ACE 球', value: '8' },
        ],
      }
    }

    if (normalized.includes('谁') && normalized.includes('发球')) {
      return {
        label: '当前发球方',
        question,
        answer: 'Sinner 正在发球。',
        highlight: 'server',
      }
    }

    if (normalized.includes('比分') || normalized.includes('score')) {
      return {
        label: '实时比分',
        question,
        answer: '比赛进入第三盘，Alcaraz 以 5–4 领先；当前局分 30–15，Sinner 发球。',
        highlight: 'score',
      }
    }

    if (normalized.includes('第一盘') || normalized.includes('first set')) {
      return {
        label: '盘分回顾',
        question,
        answer: 'Sinner 以 6–4 赢下第一盘，Alcaraz 随后以 6–4 扳回第二盘。',
        highlight: 'score',
      }
    }

    if (normalized.includes('动量') || normalized.includes('momentum') || normalized.includes('变化')) {
      return {
        label: '比赛动量',
        question,
        answer: '动量轻微转向 Sinner。他在最近 7 个短回合中赢下 5 分，但仍需要守住这个发球局。',
        highlight: 'momentum',
      }
    }

    return {
      label: '实时上下文',
      question,
      answer: '当前是第三盘，Alcaraz 以 5–4 领先，Sinner 正在发球。你还可以询问比分、发球或动量。',
      highlight: 'score',
    }
  }

  if (normalized.includes('谁赢') || normalized.includes('winner')) {
    return {
      label: '比赛结果',
      question,
      answer: 'Jannik Sinner 赢得了这场比赛。',
      highlight: 'score',
    }
  }

  if (normalized.includes('比分') || normalized.includes('score')) {
    return {
      label: '最终比分',
      question,
      answer: 'Sinner 以 6–4、4–6、6–3 击败 Alcaraz。',
      highlight: 'score',
    }
  }

  if (normalized.includes('多久') || normalized.includes('时长') || normalized.includes('long')) {
    return {
      label: '比赛时长',
      question,
      answer: '比赛持续了 2 小时 28 分。',
    }
  }

  return {
    label: '比赛总结',
    question,
    answer: 'Sinner 赢下第一盘后被 Alcaraz 扳平，随后凭借决胜盘更稳定的一发和一次关键破发，以 6–3 锁定胜局。',
    highlight: 'score',
  }
}

export function MatchPage({ initialStatus = 'upcoming' }: MatchPageProps) {
  const [status, setStatus] = useState<MatchStatus>(initialStatus)
  const [prompt, setPrompt] = useState('')
  const [submittedAnswer, setSubmittedAnswer] = useState<AssistantAnswer | null>(null)
  const [highlight, setHighlight] = useState<MatchHighlight>(null)
  const [isPending, startTransition] = useTransition()

  function focusAssistant() {
    document.getElementById('assistant')?.scrollIntoView({ behavior: 'smooth', block: 'center' })
    window.setTimeout(() => document.getElementById('match-question')?.focus(), 350)
  }

  function handleSubmit(value: string) {
    const nextAnswer = answerQuestion(value, status)
    setSubmittedAnswer(nextAnswer)
    setHighlight(nextAnswer.highlight ?? null)
    setPrompt('')
  }

  function handlePromptSelect(value: string) {
    handleSubmit(value)
    window.requestAnimationFrame(() => {
      document.getElementById('assistant')?.scrollIntoView({ behavior: 'smooth', block: 'center' })
    })
  }

  function handleStatusChange(values: string[]) {
    const nextStatus = values.at(-1) as MatchStatus | undefined
    if (!nextStatus || nextStatus === status) return

    startTransition(() => {
      setStatus(nextStatus)
      setSubmittedAnswer(null)
      setHighlight(null)
      setPrompt('')

      const url = new URL(window.location.href)
      url.searchParams.set('status', nextStatus)
      window.history.replaceState(null, '', url)
    })
  }

  return (
    <div className="min-h-screen bg-background text-foreground">
      <a
        href="#main-content"
        className="sr-only fixed left-3 top-3 z-50 rounded-lg bg-primary px-3 py-2 text-sm font-medium text-primary-foreground focus:not-sr-only"
      >
        跳至主要内容
      </a>
      <ProductHeader active="live" />

      <main
        id="main-content"
        tabIndex={-1}
        className="mx-auto flex max-w-7xl scroll-mt-20 flex-col gap-4 px-4 py-5 md:px-6 md:py-7"
      >
        <section
          className="match-reveal flex flex-col justify-between gap-3 rounded-xl border bg-card/60 p-3 sm:flex-row sm:items-center"
          aria-labelledby="status-preview-title"
        >
          <div className="flex min-w-0 items-center gap-3">
            <div className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-secondary text-primary">
              <Layers3 aria-hidden="true" className="size-4" />
            </div>
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <p id="status-preview-title" className="text-sm font-semibold">比赛状态预览</p>
                <Badge variant="outline">仅用于原型</Badge>
              </div>
              <p className="mt-1 text-sm text-muted-foreground">
                {matchStatusLabels[status].title} · {matchStatusLabels[status].description}
              </p>
            </div>
          </div>

          <ToggleGroup
            value={[status]}
            onValueChange={handleStatusChange}
            variant="outline"
            spacing={1}
            aria-label="预览比赛状态"
            aria-busy={isPending}
            className="phase-switch w-full sm:w-fit"
          >
            {statuses.map((item) => (
              <ToggleGroupItem
                key={item}
                value={item}
                className="min-h-11 flex-1 sm:min-h-9 sm:flex-none"
                aria-label={matchStatusLabels[item].title}
              >
                {matchStatusLabels[item].short}
              </ToggleGroupItem>
            ))}
          </ToggleGroup>
        </section>

        <div className="match-reveal">
          <MatchHero status={status} highlight={highlight} onAsk={focusAssistant} />
        </div>

        <div
          id="content"
          className="match-reveal grid items-start gap-4 lg:grid-cols-[minmax(0,1fr)_22rem]"
        >
          <MatchSidebar
            status={status}
            prompt={prompt}
            answer={submittedAnswer}
            onPromptChange={setPrompt}
            onPromptSelect={handlePromptSelect}
            onSubmit={handleSubmit}
          />
          <div className="min-w-0 lg:col-start-1 lg:row-start-1">
            <MatchMainColumn
              status={status}
              highlight={highlight}
              onPromptSelect={handlePromptSelect}
            />
          </div>
        </div>
      </main>

      <footer className="border-t">
        <div className="mx-auto flex max-w-7xl flex-col justify-between gap-2 px-4 py-5 text-sm text-muted-foreground sm:flex-row md:px-6">
          <span>Tennix · 比赛智能，逐分解释</span>
          <span>样例数据仅用于产品界面演示</span>
        </div>
      </footer>
    </div>
  )
}
