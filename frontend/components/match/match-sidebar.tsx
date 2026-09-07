'use client'

import type { KeyboardEvent } from 'react'
import {
  BrainCircuit,
  CircleCheck,
  CircleDot,
  Send,
  Sparkles,
} from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
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

import {
  players,
  type MatchHighlight,
  type MatchStatus,
} from './match-data'

export type AssistantAnswer = {
  label: string
  question: string
  answer: string
  highlight?: Exclude<MatchHighlight, null>
  metrics?: Array<{ label: string; value: string }>
}

type AssistantPanelProps = {
  status: MatchStatus
  prompt: string
  answer: AssistantAnswer | null
  onPromptChange: (value: string) => void
  onPromptSelect: (value: string) => void
  onSubmit: (value: string) => void
}

const promptsByStatus: Record<MatchStatus, string[]> = {
  upcoming: ['这场比赛几点开始？', '这是什么赛事？', '现在进行到哪一轮？', '比赛是什么场地？'],
  live: ['现在谁在发球？', '当前比分是多少？', '谁赢了第一盘？', 'Sinner 发球表现如何？', '比赛动量改变了吗？'],
  finished: ['谁赢了？', '最终比分是多少？', '比赛持续了多久？', '总结这场比赛'],
}

const contextDescriptions: Record<MatchStatus, string> = {
  upcoming: '已锁定本场赛程与对阵背景',
  live: '与当前比分和技术统计同步',
  finished: '基于最终比分与赛后数据',
}

function AssistantPanel({
  status,
  prompt,
  answer,
  onPromptChange,
  onPromptSelect,
  onSubmit,
}: AssistantPanelProps) {
  function submitPrompt() {
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

  return (
    <Card id="assistant" data-tone="assistant" className="scroll-mt-24">
      <CardHeader>
        <CardTitle><h2>本场比赛助手</h2></CardTitle>
        <p className="text-sm text-muted-foreground">{contextDescriptions[status]}</p>
        <CardAction>
          <Badge variant="secondary">
            <Sparkles data-icon="inline-start" aria-hidden="true" />
            Tennix AI
          </Badge>
        </CardAction>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <div className="flex flex-wrap gap-2" aria-label="本场比赛示例问题">
          {promptsByStatus[status].map((item) => (
            <Button key={item} variant="outline" size="sm" onClick={() => onPromptSelect(item)}>
              {item}
            </Button>
          ))}
        </div>

        <div aria-live="polite">
          {answer ? (
            <article className="rounded-lg bg-muted/35 p-4">
              <div className="flex items-center gap-2 text-sm font-medium text-primary">
                <BrainCircuit aria-hidden="true" className="size-4" />
                {answer.label}
              </div>
              <p className="mt-3 break-words text-sm font-medium">“{answer.question}”</p>
              <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{answer.answer}</p>

              {answer.metrics ? (
                <dl className="mt-4 grid grid-cols-3 gap-2 border-t pt-4">
                  {answer.metrics.map((metric) => (
                    <div key={metric.label} className="rounded-md bg-background/50 p-2">
                      <dt className="text-[11px] leading-tight text-muted-foreground">{metric.label}</dt>
                      <dd className="mt-1 font-mono text-lg font-semibold text-primary tabular-nums">{metric.value}</dd>
                    </div>
                  ))}
                </dl>
              ) : null}

              <div className="mt-3 flex items-center gap-2 text-xs text-muted-foreground">
                <CircleCheck aria-hidden="true" className="size-4" />
                已连接本场比赛上下文
              </div>
            </article>
          ) : (
            <div className="flex min-h-32 flex-col items-center justify-center gap-3 rounded-lg border border-dashed bg-muted/15 p-4 text-center">
              <div className="flex size-9 items-center justify-center rounded-full bg-secondary text-primary">
                <BrainCircuit aria-hidden="true" className="size-4" />
              </div>
              <div>
                <p className="text-sm font-medium">无需重复球员姓名</p>
                <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
                  直接询问时间、比分、发球或比赛结果。
                </p>
              </div>
            </div>
          )}
        </div>
      </CardContent>
      <CardFooter>
        <form
          className="w-full"
          onSubmit={(event) => {
            event.preventDefault()
            submitPrompt()
          }}
        >
          <label htmlFor="match-question" className="sr-only">向 Tennix 询问本场比赛</label>
          <InputGroup className="h-11">
            <InputGroupInput
              id="match-question"
              name="match-question"
              value={prompt}
              onChange={(event) => onPromptChange(event.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="例如：现在谁在发球？"
              autoComplete="off"
            />
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

function KeyFact({ label, value, detail }: { label: string; value: string; detail: string }) {
  return (
    <div className="flex items-start justify-between gap-4 py-3">
      <div className="min-w-0">
        <p className="text-sm text-muted-foreground">{label}</p>
        <p className="mt-1 text-sm leading-relaxed">{detail}</p>
      </div>
      <span className="shrink-0 font-mono text-sm font-semibold tabular-nums">{value}</span>
    </div>
  )
}

function KeyFactsCard() {
  return (
    <Card>
      <CardHeader>
        <CardTitle><h2>关键事实</h2></CardTitle>
        <p className="text-sm text-muted-foreground">理解这场对局所需的背景</p>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 gap-3 rounded-lg bg-muted/30 p-3">
          {players.map((player) => (
            <div key={player.id} className="min-w-0">
              <p className="truncate text-sm text-muted-foreground">{player.shortName}</p>
              <p className="mt-1 font-mono text-lg font-semibold">#{player.rank}</p>
            </div>
          ))}
        </div>
        <div className="mt-3 divide-y">
          <KeyFact label="交手记录" value="7–6" detail="Sinner 微弱领先" />
          <KeyFact label="近 10 场" value="9–1 / 8–2" detail="双方均处于高水平状态" />
          <KeyFact label="室内硬地" value="84% / 79%" detail="过去 24 个月胜率" />
          <KeyFact label="比赛重要性" value="半决赛" detail="胜者进入赛季收官战" />
        </div>
      </CardContent>
    </Card>
  )
}

function MarketCard() {
  return (
    <Card id="market-intelligence" data-tone="market">
      <CardHeader>
        <CardTitle><h2>市场智能</h2></CardTitle>
        <p className="text-sm text-muted-foreground">后续决策能力占位</p>
        <CardAction><Badge variant="outline">P3 后可用</Badge></CardAction>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <dl className="grid grid-cols-3 gap-3 rounded-lg border border-dashed bg-muted/15 p-3">
          <div>
            <dt className="text-xs text-muted-foreground">模型概率</dt>
            <dd className="mt-1 font-mono text-xl font-semibold">—</dd>
          </div>
          <div>
            <dt className="text-xs text-muted-foreground">市场概率</dt>
            <dd className="mt-1 font-mono text-xl font-semibold">—</dd>
          </div>
          <div>
            <dt className="text-xs text-muted-foreground">优势</dt>
            <dd className="mt-1 font-mono text-xl font-semibold">—</dd>
          </div>
        </dl>
        <div className="flex items-start gap-2 text-sm leading-relaxed text-muted-foreground">
          <CircleDot aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
          P3 将在此加入公允价、置信度与建议，不改变当前比赛页结构。
        </div>
      </CardContent>
    </Card>
  )
}

export function MatchSidebar(props: AssistantPanelProps) {
  return (
    <aside className="flex min-w-0 flex-col gap-4 lg:sticky lg:top-20 lg:col-start-2 lg:row-start-1 lg:self-start" aria-label="比赛助手与关键事实">
      <AssistantPanel {...props} />
      <KeyFactsCard />
      <MarketCard />
    </aside>
  )
}
