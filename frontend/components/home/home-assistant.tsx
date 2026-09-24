'use client'

import { useEffect, useRef, type FormEvent, type KeyboardEvent } from 'react'
import Link from 'next/link'
import {
  BrainCircuit,
  CheckCircle2,
  RefreshCw,
  Send,
  Sparkles,
} from 'lucide-react'

import { MatchResultCard } from '@/components/home/home-match-result-card'
import { HomePlayerHistory } from '@/components/home/home-player-history'
import { PlayerCountry } from '@/components/player-country'
import { OpportunityRow } from '@/components/markets/opportunity-row'
import { ChatWarnings } from '@/components/chat-warnings'
import { MarkdownAnswer } from '@/components/markdown-answer'
import { userFacingApiError } from '@/lib/api/user-facing-errors'
import { chatProgressLabel, type ChatViewState } from '@/hooks/use-chat-stream'
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
import type { StructuredData } from '@/lib/api/types'
import type { HomeMatchViewModel } from '@/lib/view-models'
import { countryPresentation, toHomeMatch } from '@/lib/view-models'
import { toOpportunityRow } from '@/lib/p3-view-models'
import { getChatAnswerLabel } from '@/lib/chat-answer'
import { playerHistoryTitle } from '@/lib/player-history-view'

function historyItemsOf(chat: ChatViewState): StructuredData[] {
  return chat.dataItems.filter((item) => item.kind === 'player_history')
}

function answerTitle(
  chat: ChatViewState,
  cards: HomeMatchViewModel[],
  historyItems: StructuredData[],
): string {
  if (historyItems.length === 1) {
    return playerHistoryTitle(historyItems[0])
  }
  if (historyItems.length > 1) {
    return '球员赛果与战绩'
  }
  if (chat.data?.kind === 'market_opportunities') return '市场机会'
  if (chat.data?.kind === 'match_decision') return '本场判断结果'
  if (cards.length > 0) {
    return `${cards[0].players[0]} 对阵 ${cards[0].players[1]}`
  }
  if (chat.data?.kind === 'unsupported') {
    const reason = chat.data.metadata?.reason
    if (reason === 'p3_disabled') return '市场功能暂未开放'
    if (reason === undefined) return '历史结果查询暂不支持'
    return '暂不支持此类查询'
  }
  if (chat.data?.kind === 'player_resolution') {
    if (chat.data.resolution?.status === 'ambiguous') return '多位候选球员，请选择'
    if (chat.data.resolution?.status === 'not_found') return '未找到该球员'
    return '已解析球员'
  }
  // `没有符合条件的比赛` is reserved for current/live/upcoming discovery.
  if (chat.data) return '没有符合条件的比赛'
  if (chat.error) return '回答暂时无法生成'
  return '正在整理回答'
}

function errorSummary(error: ChatViewState['error']): string {
  if (!error) return ''
  if (error.code === 'rate_limited') {
    const retryAfter = error.details.retry_after
    const retryLabel =
      typeof retryAfter === 'string' || typeof retryAfter === 'number'
        ? `${retryAfter} 秒后`
        : '稍后'
    return `数据服务配额暂时用完，请在${retryLabel}重试。`
  }
  return userFacingApiError(error.code, 'assistant')
}

type HomeAssistantProps = {
  prompt: string
  chat: ChatViewState
  busy: boolean
  onPromptChange: (value: string) => void
  onSubmit: (value: string) => void
}

export function HomeAssistant({
  prompt,
  chat,
  busy,
  onPromptChange,
  onSubmit,
}: HomeAssistantProps) {
  function submitPrompt(event?: FormEvent<HTMLFormElement>) {
    event?.preventDefault()
    if (busy) return
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

  function followUp(match: HomeMatchViewModel) {
    onPromptChange(`${match.players[0]} 对阵 ${match.players[1]} 的比赛场地是什么？`)
    window.requestAnimationFrame(() => document.getElementById('home-question')?.focus())
  }

  const historyItems = historyItemsOf(chat)
  const cards = [
    ...new Map(
      chat.dataItems
        .filter(({ kind }) => kind === 'matches' || kind === 'match')
        .flatMap(({ matches }) => matches)
        .map((match) => [match.id, toHomeMatch(match)] as const),
    ).values(),
  ]
  const opportunityResults = chat.dataItems
    .filter(({ kind }) => kind === 'market_opportunities')
    .map(({ market_opportunities: result }) => result)
    .filter((result): result is NonNullable<typeof result> => result !== null && result !== undefined)
  const opportunitiesTruncated = opportunityResults.some((result) => result.truncated)
  const opportunityRows = [
    ...new Map(
      opportunityResults
        .flatMap(({ opportunities }) => opportunities)
        .map((opportunity) => [
          opportunity.market_id,
          toOpportunityRow(opportunity, new Date()),
        ] as const),
    ).values(),
  ]
  const hasAnswer =
    chat.phase !== 'idle' &&
    (Boolean(chat.data) || Boolean(chat.text) || Boolean(chat.error) || chat.warnings.length > 0)
  const summary =
    chat.text ||
    errorSummary(chat.error)
  const structuredResultsRef = useRef<HTMLDivElement>(null)
  const structuredCount =
    cards.length + historyItems.length + opportunityRows.length + Number(opportunitiesTruncated)

  useEffect(() => {
    if ((chat.phase !== 'success' && chat.phase !== 'error') || structuredCount === 0) return

    const results = structuredResultsRef.current
    if (!results) return

    const rect = results.getBoundingClientRect()
    if (rect.height > 0 && rect.top >= 0 && rect.bottom <= window.innerHeight) return

    const prefersReducedMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false
    results.scrollIntoView({
      behavior: prefersReducedMotion ? 'auto' : 'smooth',
      block: 'start',
    })
  }, [chat.phase, structuredCount])

  return (
    <Card id="assistant" data-tone="assistant" className="scroll-mt-24">
      <CardHeader>
        <CardTitle>
          <h2>网球问答</h2>
        </CardTitle>
        <p className="text-sm text-muted-foreground">关于比赛、赛程和球员的回答</p>
        <CardAction>
          <Badge variant="secondary">
            <Sparkles data-icon="inline-start" aria-hidden="true" />
            Tennix AI
          </Badge>
        </CardAction>
      </CardHeader>

      <CardContent className="flex flex-col gap-4">
        <div aria-live="polite" className="flex flex-col gap-3">
          {hasAnswer ? (
            <>
              <article className="rounded-xl bg-muted/30 p-4">
                <div className="flex items-center justify-between gap-3">
                  <span className="flex items-center gap-2 text-xs font-semibold text-primary">
                    <BrainCircuit aria-hidden="true" className="size-4" />
                    {getChatAnswerLabel(chat, 'global')}
                  </span>
                  {chat.error || cards.length === 0 ? null : (
                    <CheckCircle2 aria-label="包含比赛信息卡" className="size-4 text-muted-foreground" />
                  )}
                </div>
                <h3 className="mt-2 text-balance text-lg font-semibold">{answerTitle(chat, cards, historyItems)}</h3>
                {summary ? <MarkdownAnswer content={summary} /> : null}
                <ChatWarnings warnings={chat.warnings} />
                {chat.phase === 'loading' || chat.phase === 'streaming' ? (
                  <p className="mt-2 text-xs text-muted-foreground">
                    {chatProgressLabel(chat.stage, chat.progress)}
                  </p>
                ) : null}
              </article>

              {structuredCount > 0 ? (
                <div
                  ref={structuredResultsRef}
                  className="scroll-mt-24 flex flex-col gap-3"
                  aria-label="相关比赛和市场信息"
                >
                  {historyItems.length > 0 ? (
                    <HomePlayerHistory items={historyItems} onFollowUp={followUp} />
                  ) : null}
                  {cards.map((match) => (
                    <MatchResultCard key={match.id} match={match} onFollowUp={followUp} />
                  ))}
                  {opportunityRows.map((opportunity) => (
                    <OpportunityRow key={opportunity.id} opportunity={opportunity} />
                  ))}
                  {opportunitiesTruncated ? (
                    <p className="text-xs text-muted-foreground" role="status">
                      还有其他符合条件的机会，以下仅展示部分结果。
                    </p>
                  ) : null}
                </div>
              ) : null}

              {chat.data?.kind === 'player_resolution'
              && chat.data.resolution?.status === 'ambiguous' ? (
                <div className="flex flex-col gap-2" aria-label="候选球员">
                  {chat.data.resolution.candidates.map((candidate) => {
                    const country = countryPresentation(
                      candidate.player.country_code,
                      candidate.player.country_alpha2 ?? null,
                    )
                    return (
                      <Link
                        key={candidate.player.id}
                        href={`/players/${candidate.player.id}`}
                        className="flex items-center justify-between gap-3 rounded-xl border bg-card/60 px-4 py-3 text-sm transition-colors hover:bg-muted/40"
                      >
                        <span className="font-medium">
                          {candidate.player.localized_name
                            ? `${candidate.player.name}（${candidate.player.localized_name}）`
                            : candidate.player.name}
                        </span>
                        <span className="flex items-center gap-2 text-xs text-muted-foreground">
                          <PlayerCountry player={country} />
                          <span>{country.countryName}</span>
                          <span>
                            {candidate.current_rank ? `#${candidate.current_rank}` : '暂无当前排名'}
                          </span>
                        </span>
                      </Link>
                    )
                  })}
                </div>
              ) : null}

              {chat.error ? (
                <Button variant="outline" onClick={() => onSubmit(chat.question)} aria-label="重试提问">
                  <RefreshCw data-icon="inline-start" aria-hidden="true" />
                  重试提问
                </Button>
              ) : null}
            </>
          ) : chat.phase === 'loading' ? (
            <div className="flex min-h-36 flex-col items-center justify-center gap-3 rounded-xl border border-dashed bg-muted/15 p-5 text-center">
              <div className="flex size-10 items-center justify-center rounded-full bg-secondary text-primary">
                <BrainCircuit aria-hidden="true" className="size-5" />
              </div>
              <p className="font-medium">{chatProgressLabel(chat.stage, chat.progress)}</p>
            </div>
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
              <InputGroupButton type="submit" size="icon-sm" aria-label="发送问题" disabled={busy}>
                <Send aria-hidden="true" />
              </InputGroupButton>
            </InputGroupAddon>
          </InputGroup>
        </form>
      </CardFooter>
    </Card>
  )
}
