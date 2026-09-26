'use client'

import { useCallback, useEffect, useState, useTransition } from 'react'
import Link from 'next/link'
import { Layers3 } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group'
import { useChatStream } from '@/hooks/use-chat-stream'
import { useDecisionStream } from '@/hooks/use-decision-stream'
import { useMatchStream } from '@/hooks/use-match-stream'
import { userFacingApiError } from '@/lib/api/user-facing-errors'
import type { MatchViewModel } from '@/lib/view-models'
import { toMatchViewModel } from '@/lib/view-models'
import {
  appendTrajectoryPoint,
  toChartSides,
  toDecisionSummaryModel,
  toEvidenceModel,
  toPaperModel,
  workbenchOverlay,
  type TrajectoryPointModel,
} from '@/lib/p3-workbench-models'

import {
  matchStatusLabels,
  type MatchHighlight,
  type MatchStatus,
} from './match/match-data'
import { DecisionEvidenceLive } from './match/decision-evidence-live'
import { DecisionSummaryLive } from './match/decision-summary-live'
import { ProductHeader } from './match/match-header'
import { MatchHero } from './match/match-hero'
import {
  MatchMainColumn,
  OverviewCard,
  ScoreProgressCard,
  StatsCard,
} from './match/match-main'
import { MatchMomentumCard } from './match/match-momentum'
import { buildPreviewMatch } from './match/match-preview-data'
import { AssistantPanel, KeyFactsCard, MatchSidebar } from './match/match-sidebar'
import { PaperLifecycleLive } from './match/paper-lifecycle-live'
import { ProbabilityMarketChart } from './match/probability-market-chart'

const statuses = Object.keys(matchStatusLabels) as MatchStatus[]

type MatchPageProps =
  | { matchId: string; previewMatch?: undefined; preview?: false }
  | { matchId?: undefined; previewMatch: MatchViewModel; preview: true }

type LoadState = 'loading' | 'success' | 'error' | 'notfound'

export function MatchPage({ matchId, previewMatch, preview = false }: MatchPageProps) {
  const isPreview = preview && previewMatch !== undefined

  const [previewStatus, setPreviewStatus] = useState<MatchStatus>(
    isPreview ? previewMatch.visualStatus === 'unavailable' ? 'upcoming' : previewMatch.visualStatus : 'upcoming',
  )
  const previewViewModel = isPreview ? buildPreviewMatch(previewStatus) : null

  const [match, setMatch] = useState<MatchViewModel | null>(null)
  const [loadState, setLoadState] = useState<LoadState>('loading')
  const [loadErrorCode, setLoadErrorCode] = useState<string | null>(null)
  const [highlight, setHighlight] = useState<MatchHighlight>(null)
  const [isPending, startTransition] = useTransition()

  const chat = useChatStream('match', isPreview ? undefined : matchId)

  const stream = useMatchStream(isPreview ? undefined : matchId)
  // The decision stream keeps its own cursor; a decision gap never touches
  // the sports stream above and vice versa.
  const decisionStream = useDecisionStream(isPreview ? undefined : matchId)

  const [trajectory, setTrajectory] = useState<TrajectoryPointModel[]>([])
  useEffect(() => {
    setTrajectory([])
  }, [matchId])
  const decision = isPreview ? null : decisionStream.decision
  useEffect(() => {
    if (!decision) return
    setTrajectory((points) => appendTrajectoryPoint(points, decision))
  }, [decision])

  const load = useCallback(async () => {
    await stream.refresh()
  }, [stream.refresh])

  useEffect(() => {
    if (isPreview || !stream.snapshot) return
    setMatch(toMatchViewModel(stream.snapshot.match))
    setLoadErrorCode(null)
    setLoadState('success')
  }, [isPreview, stream.snapshot])

  useEffect(() => {
    if (isPreview) return
    if (stream.phase === 'loading') {
      setLoadState('loading')
    } else if (stream.phase === 'error') {
      setLoadErrorCode(stream.errorCode)
      setLoadState(stream.errorCode === 'not_found' ? 'notfound' : 'error')
    }
  }, [isPreview, stream.phase, stream.errorCode])

  useEffect(() => {
    if (isPreview || !chat.state.data) return
    const data = chat.state.data
    if (data.kind === 'match' && data.matches[0]) {
      const view = toMatchViewModel(data.matches[0])
      setMatch(view)
      setHighlight(view.visualStatus === 'live' ? 'score' : null)
    }
  }, [chat.state.data, isPreview])

  function focusAssistant() {
    document.getElementById('assistant')?.scrollIntoView({ behavior: 'smooth', block: 'center' })
    window.setTimeout(() => document.getElementById('match-question')?.focus(), 350)
  }

  function handlePromptSelect(value: string) {
    if (!isPreview) {
      void chat.send(value)
    }
    window.requestAnimationFrame(() => {
      document.getElementById('assistant')?.scrollIntoView({ behavior: 'smooth', block: 'center' })
    })
  }

  function handleStatusChange(values: string[]) {
    const nextStatus = values.at(-1) as MatchStatus | undefined
    if (!nextStatus || nextStatus === previewStatus) return

    startTransition(() => {
      setPreviewStatus(nextStatus)
      setHighlight(null)

      const url = new URL(window.location.href)
      url.searchParams.set('status', nextStatus)
      window.history.replaceState(null, '', url)
    })
  }

  const activeViewModel = isPreview ? previewViewModel : match

  // Workbench models: one current-action source (the server snapshot);
  // React never derives probability, edge, fill, settlement or lifecycle.
  const playerNameById: Record<string, string> = Object.fromEntries(
    (stream.snapshot?.match.players ?? []).map((player) => [player.id, player.name]),
  )
  const playerLocalizedNameById: Record<string, string | null> = Object.fromEntries(
    (stream.snapshot?.match.players ?? []).map((player) => [player.id, player.localized_name?.trim() || null]),
  )
  const selectionName =
    decision?.target_player_id != null
      ? (playerNameById[decision.target_player_id] ?? null)
      : null
  const selectionLocalizedName =
    decision?.target_player_id != null
      ? (playerLocalizedNameById[decision.target_player_id] ?? null)
      : null
  const summaryModel = decision
    ? toDecisionSummaryModel(decision, selectionName, new Date(), selectionLocalizedName)
    : null
  const evidenceModel = decision ? toEvidenceModel(decision) : null
  const paperModel = decision ? toPaperModel(decision) : null
  const chartSides = decision
    ? toChartSides(decision, playerNameById, playerLocalizedNameById)
    : []
  const hasWorkbench = !isPreview && decision !== null && activeViewModel !== null

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
        {isPreview ? (
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
                  {matchStatusLabels[previewStatus].title} · {matchStatusLabels[previewStatus].description}
                </p>
              </div>
            </div>

            <ToggleGroup
              value={[previewStatus]}
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
        ) : null}

        {isPreview && activeViewModel ? (
          <>
            <div className="match-reveal">
              <MatchHero match={activeViewModel} highlight={highlight} onAsk={focusAssistant} preview />
            </div>

            <div
              id="content"
              className="match-reveal grid items-start gap-4 lg:grid-cols-[minmax(0,1fr)_22rem]"
            >
              <MatchSidebar
                match={activeViewModel}
                preview
                chat={null}
                onSubmit={() => {}}
              />
              <div className="min-w-0 lg:col-start-1 lg:row-start-1">
                <MatchMainColumn
                  match={activeViewModel}
                  preview
                  highlight={highlight}
                  onPromptSelect={handlePromptSelect}
                />
              </div>
            </div>
          </>
        ) : loadState === 'loading' ? (
          <div className="match-reveal flex min-h-64 flex-col items-center justify-center gap-3 rounded-xl border border-dashed bg-muted/15 p-6 text-center">
            <p className="text-sm font-medium">正在加载比赛信息…</p>
          </div>
        ) : loadState === 'notfound' ? (
          <div className="match-reveal flex min-h-64 flex-col items-center justify-center gap-3 rounded-xl border border-dashed bg-muted/15 p-6 text-center">
            <p className="text-sm font-medium">未找到这场比赛</p>
            <p className="text-sm text-muted-foreground">比赛可能已结束，或此链接已失效。你可以返回首页搜索。</p>
            <Button render={<Link href="/" />} variant="outline">返回首页</Button>
          </div>
        ) : loadState === 'error' ? (
          <div className="match-reveal flex min-h-64 flex-col items-center justify-center gap-3 rounded-xl border border-dashed bg-muted/15 p-6 text-center">
            <p className="text-sm font-medium">{userFacingApiError(loadErrorCode, 'match')}</p>
            <Button variant="outline" onClick={() => void load()} aria-label="重试加载比赛">
              重试加载
            </Button>
          </div>
        ) : activeViewModel ? (
          <>
            {stream.phase === 'reconnecting' || stream.connectionNotice === 'reconnecting' ? (
              <p role="status" className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-100">
                比分更新中，请稍候。
              </p>
            ) : stream.connectionNotice === 'restored' ? (
              <p role="status" className="rounded-lg border border-primary/30 bg-primary/10 px-4 py-3 text-sm text-primary">
                比分已更新。
              </p>
            ) : stream.phase === 'stale' ? (
              <p role="status" className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-100">
                比分可能暂时未更新；返回页面后会自动刷新。
              </p>
            ) : null}
            <div className="match-reveal">
              <MatchHero
                match={activeViewModel}
                highlight={highlight}
                onAsk={focusAssistant}
                onRefresh={() => void load()}
              />
            </div>

            {hasWorkbench && summaryModel ? (
              <>
                <div className="match-reveal">
                  <DecisionSummaryLive decision={summaryModel} onAsk={focusAssistant} />
                </div>
                {decisionStream.degraded ? (
                  <p role="status" className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-100">
                    判断暂时无法更新，仍显示最近一次结果；比赛实时比分不受影响。
                  </p>
                ) : null}
                <div
                  id="content"
                  className="match-reveal grid items-start gap-4 lg:grid-cols-[minmax(0,1fr)_22rem]"
                >
                  <div className="min-w-0 lg:col-start-1 lg:row-start-2">
                    <ScoreProgressCard match={activeViewModel} preview={false} highlight={highlight} />
                  </div>
                  <aside className="min-w-0 lg:col-start-2 lg:row-start-2" aria-label="比赛关键事实">
                    <KeyFactsCard match={activeViewModel} preview={false} />
                  </aside>
                  <div className="min-w-0 lg:col-start-1 lg:row-start-1">
                    <OverviewCard match={activeViewModel} preview={false} />
                  </div>
                  <div className="min-w-0 lg:col-start-1 lg:row-start-3">
                    <ProbabilityMarketChart
                      sides={chartSides}
                      trajectory={trajectory}
                      overlay={decision ? workbenchOverlay(decision) : 'none'}
                    />
                  </div>
                  <div className="min-w-0 lg:col-start-1 lg:row-start-4">
                    {evidenceModel ? <DecisionEvidenceLive evidence={evidenceModel} /> : null}
                  </div>
                  <div className="min-w-0 lg:col-start-1 lg:row-start-5">
                    <StatsCard
                      match={activeViewModel}
                      preview={false}
                      highlight={highlight}
                      snapshot={stream.snapshot}
                    />
                  </div>
                  <div className="min-w-0 lg:col-start-1 lg:row-start-6">
                    <MatchMomentumCard
                      match={activeViewModel}
                      preview={false}
                      highlight={highlight}
                      snapshot={stream.snapshot}
                    />
                  </div>
                  <div className="min-w-0 lg:col-start-1 lg:row-start-7">
                    {paperModel ? <PaperLifecycleLive paper={paperModel} /> : null}
                  </div>
                  <aside
                    className="min-w-0 lg:sticky lg:top-20 lg:col-start-2 lg:row-start-1"
                    aria-label="比赛助手"
                  >
                    <AssistantPanel
                      match={activeViewModel}
                      preview={false}
                      chat={chat.state}
                      onSubmit={(value) => void chat.send(value)}
                      currentStateVersion={stream.snapshot?.state_version ?? null}
                    />
                  </aside>
                </div>
              </>
            ) : (
              <div
                id="content"
                className="match-reveal grid items-start gap-4 lg:grid-cols-[minmax(0,1fr)_22rem]"
              >
                <MatchSidebar
                  match={activeViewModel}
                  preview={false}
                  chat={chat.state}
                  onSubmit={(value) => void chat.send(value)}
                  currentStateVersion={stream.snapshot?.state_version ?? null}
                />
                <div className="min-w-0 lg:col-start-1 lg:row-start-1">
                  <MatchMainColumn
                    match={activeViewModel}
                    preview={false}
                    highlight={highlight}
                    onPromptSelect={handlePromptSelect}
                    snapshot={stream.snapshot}
                  />
                </div>
              </div>
            )}
          </>
        ) : null}
      </main>

      <footer className="border-t">
        <div className="mx-auto flex max-w-7xl flex-col justify-between gap-2 px-4 py-5 text-sm text-muted-foreground sm:flex-row md:px-6">
          <span>Tennix · 比赛智能，逐分解释</span>
          <span>
            {isPreview ? '样例数据仅供参考，不代表实时比赛' : '比赛时间为北京时间'}
          </span>
        </div>
      </footer>
    </div>
  )
}
