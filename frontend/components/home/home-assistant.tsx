'use client'

import type { FormEvent, KeyboardEvent } from 'react'
import Link from 'next/link'
import {
  ArrowRight,
  BrainCircuit,
  CheckCircle2,
  Clock3,
  MapPin,
  Radio,
  Send,
  Sparkles,
} from 'lucide-react'

import {
  homeExampleQueries,
  type HomeAnswer,
  type HomeMatchResult,
} from '@/components/home/home-data'
import { Badge } from '@/components/ui/badge'
import { Button, buttonVariants } from '@/components/ui/button'
import {
  Card,
  CardAction,
  CardContent,
  CardFooter,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import {
  InputGroup,
  InputGroupAddon,
  InputGroupButton,
  InputGroupInput,
} from '@/components/ui/input-group'
import { cn } from '@/lib/utils'

const statusDetails = {
  upcoming: { label: '即将开始', variant: 'outline' as const },
  live: { label: '直播', variant: 'destructive' as const },
  finished: { label: '已完赛', variant: 'secondary' as const },
}

function MatchResultCard({
  match,
  onFollowUp,
}: {
  match: HomeMatchResult
  onFollowUp: (match: HomeMatchResult) => void
}) {
  const status = statusDetails[match.status]

  return (
    <Card size="sm" className="bg-background/45" data-testid={`home-match-${match.status}`}>
      <CardHeader className="border-b">
        <CardTitle>
          <h3 className="text-pretty text-base">
            {match.players[0]} <span className="text-muted-foreground">vs</span> {match.players[1]}
          </h3>
        </CardTitle>
        <p className="text-xs text-muted-foreground">{match.tournament} · {match.round}</p>
        <CardAction>
          <Badge variant={status.variant} role="status">
            {match.status === 'live' ? (
              <span className="live-pulse size-1.5 rounded-full bg-current" aria-hidden="true" />
            ) : null}
            {status.label}
          </Badge>
        </CardAction>
      </CardHeader>

      <CardContent className="flex flex-col gap-4">
        {match.score ? (
          <div className="rounded-lg bg-muted/25 p-3">
            <div className="mb-2 flex items-center justify-between gap-3 text-xs text-muted-foreground">
              <span className="flex items-center gap-1.5 text-live">
                <Radio aria-hidden="true" className="size-3.5" />
                {match.score.currentSet}
              </span>
              <span>{match.score.note}</span>
            </div>
            <div className="flex flex-col gap-2">
              {match.score.rows.map((row) => (
                <div key={row.player} className="grid grid-cols-[minmax(0,1fr)_auto_auto] items-center gap-3">
                  <span className="flex min-w-0 items-center gap-2 font-medium">
                    {row.serving ? <span className="size-1.5 shrink-0 rounded-full bg-primary" aria-label="发球方" /> : null}
                    <span className="truncate">{row.player}</span>
                  </span>
                  <span className="font-mono text-sm text-muted-foreground tabular-nums">{row.sets.join('  ')}</span>
                  <span className="min-w-7 text-right font-mono text-lg font-semibold text-primary tabular-nums">{row.points}</span>
                </div>
              ))}
            </div>
          </div>
        ) : null}

        <dl className="grid grid-cols-2 gap-x-4 gap-y-3 text-xs">
          <div>
            <dt className="text-muted-foreground">时间</dt>
            <dd className="mt-1 flex items-center gap-1.5 font-medium">
              <Clock3 aria-hidden="true" className="size-3.5 text-primary" />
              {match.time}
            </dd>
          </div>
          <div>
            <dt className="text-muted-foreground">场地</dt>
            <dd className="mt-1 font-medium">{match.surface}</dd>
          </div>
          <div className="col-span-2">
            <dt className="text-muted-foreground">地点</dt>
            <dd className="mt-1 flex items-center gap-1.5 font-medium">
              <MapPin aria-hidden="true" className="size-3.5 text-primary" />
              {match.location}
            </dd>
          </div>
        </dl>
      </CardContent>

      <CardFooter className="flex-col gap-2 sm:flex-row">
        <Link
          href={match.href}
          className={cn(buttonVariants(), 'w-full sm:flex-1')}
          aria-label={`${match.actionLabel ?? '打开比赛'}：${match.players[0]} 对阵 ${match.players[1]}`}
        >
          {match.actionLabel ?? '打开比赛'}
          <ArrowRight data-icon="inline-end" aria-hidden="true" />
        </Link>
        <Button variant="outline" className="w-full sm:flex-1" onClick={() => onFollowUp(match)}>
          继续追问
        </Button>
      </CardFooter>
    </Card>
  )
}

type HomeAssistantProps = {
  prompt: string
  answer: HomeAnswer | null
  onPromptChange: (value: string) => void
  onSubmit: (value: string) => void
  onPromptSelect: (value: string) => void
}

export function HomeAssistant({
  prompt,
  answer,
  onPromptChange,
  onSubmit,
  onPromptSelect,
}: HomeAssistantProps) {
  function submitPrompt(event?: FormEvent<HTMLFormElement>) {
    event?.preventDefault()
    const value = prompt.trim()
    if (!value) return
    onSubmit(value)
  }

  function handleKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key !== 'Enter') return
    if (event.nativeEvent.isComposing || event.keyCode === 229) {
      event.preventDefault()
      return
    }
    event.preventDefault()
    submitPrompt()
  }

  function followUp(match: HomeMatchResult) {
    onPromptChange(`${match.players[0]} 对阵 ${match.players[1]} 的比赛场地是什么？`)
    window.requestAnimationFrame(() => document.getElementById('home-question')?.focus())
  }

  return (
    <Card id="assistant" data-tone="assistant" className="scroll-mt-24">
      <CardHeader>
        <CardTitle>
          <h2>全局网球助手</h2>
        </CardTitle>
        <p className="text-sm text-muted-foreground">发现比赛、赛程与球员</p>
        <CardAction>
          <Badge variant="secondary">
            <Sparkles data-icon="inline-start" aria-hidden="true" />
            Tennix AI
          </Badge>
        </CardAction>
      </CardHeader>

      <CardContent className="flex flex-col gap-4">
        <div className="flex flex-wrap gap-2" aria-label="示例问题">
          {homeExampleQueries.map((item) => (
            <Button key={item} variant="outline" size="sm" onClick={() => onPromptSelect(item)}>
              {item}
            </Button>
          ))}
        </div>

        <div aria-live="polite" className="flex flex-col gap-3">
          {answer ? (
            <>
              <article className="rounded-xl bg-muted/30 p-4">
                <div className="flex items-center justify-between gap-3">
                  <span className="flex items-center gap-2 text-xs font-semibold text-primary">
                    <BrainCircuit aria-hidden="true" className="size-4" />
                    {answer.label}
                  </span>
                  <CheckCircle2 aria-label="已核验" className="size-4 text-muted-foreground" />
                </div>
                <p className="mt-3 break-words text-xs text-muted-foreground">“{answer.question}”</p>
                <h3 className="mt-2 text-balance text-lg font-semibold">{answer.title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{answer.summary}</p>
              </article>

              <div className="flex flex-col gap-3" aria-label="结构化比赛结果">
                {answer.matches.map((match) => (
                  <MatchResultCard key={match.id} match={match} onFollowUp={followUp} />
                ))}
              </div>

              <p className="font-mono text-[11px] text-muted-foreground">{answer.source}</p>
            </>
          ) : (
            <div className="flex min-h-36 flex-col items-center justify-center gap-3 rounded-xl border border-dashed bg-muted/15 p-5 text-center">
              <div className="flex size-10 items-center justify-center rounded-full bg-secondary text-primary">
                <BrainCircuit aria-hidden="true" className="size-5" />
              </div>
              <div>
                <p className="font-medium">从一个网球问题开始</p>
                <p className="mt-1 text-sm leading-relaxed text-muted-foreground">
                  Tennix 会返回可操作的比赛卡片，而不只是聊天文字。
                </p>
              </div>
            </div>
          )}
        </div>
      </CardContent>

      <CardFooter>
        <form className="w-full" onSubmit={submitPrompt}>
          <label htmlFor="home-question" className="sr-only">继续向 Tennix 提问</label>
          <InputGroup className="h-11 bg-background/55">
            <InputGroupInput
              id="home-question"
              name="home-question"
              value={prompt}
              onChange={(event) => onPromptChange(event.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="例如：Sinner 今晚几点比赛？"
              autoComplete="off"
            />
            <InputGroupAddon align="inline-start">
              <BrainCircuit aria-hidden="true" />
            </InputGroupAddon>
            <InputGroupAddon align="inline-end">
              <InputGroupButton type="submit" size="icon-sm" aria-label="发送问题">
                <Send aria-hidden="true" />
              </InputGroupButton>
            </InputGroupAddon>
          </InputGroup>
        </form>
      </CardFooter>
    </Card>
  )
}
