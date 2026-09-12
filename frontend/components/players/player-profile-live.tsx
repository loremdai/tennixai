'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { AlertTriangle, ArrowLeft } from 'lucide-react'

import { ProductHeader } from '@/components/match/match-header'
import { PlayerCurrentStatus } from '@/components/players/player-current-status'
import type {
  CompetitionTier,
  MatchOutcome,
  PlayerHistoryState,
} from '@/components/players/player-preview-data'
import { PlayerProfileHeader } from '@/components/players/player-profile-header'
import { PlayerResults } from '@/components/players/player-results'
import { PlayerSeasonSummary } from '@/components/players/player-season-summary'
import { Button, buttonVariants } from '@/components/ui/button'
import { ApiError, getPlayerProfile, getPlayerResults } from '@/lib/api/client'
import type { PlayerProfileViewDto, PlayerResultPageDto } from '@/lib/api/types'
import {
  resultsHistoryState,
  toCurrentStatus,
  toProfilePreview,
  toResultPreview,
  toSeasonSummary,
  viewTierToCircuitTier,
} from '@/lib/player-view-models'
import { cn } from '@/lib/utils'

type ProfileState =
  | { phase: 'loading' }
  | { phase: 'error'; message: string }
  | { phase: 'not_found' }
  | { phase: 'ready'; view: PlayerProfileViewDto }

type ResultsState =
  | { phase: 'loading' }
  | { phase: 'error' }
  | { phase: 'ready'; page: PlayerResultPageDto }

function outcomeParam(outcome: 'ALL' | MatchOutcome): 'all' | 'won' | 'lost' {
  if (outcome === 'win') return 'won'
  if (outcome === 'loss') return 'lost'
  return 'all'
}

function ProfilePageSkeleton() {
  return (
    <div className="min-h-dvh bg-background text-foreground" aria-busy="true">
      <ProductHeader active="players" />
      <main className="mx-auto flex w-full max-w-7xl flex-col gap-5 px-4 py-6 md:px-6 md:py-8">
        <span className="sr-only">正在加载球员资料</span>
        <span className="h-4 w-32 animate-pulse rounded-md bg-muted" />
        <span className="h-56 w-full animate-pulse rounded-xl bg-muted" />
        <span className="h-40 w-full animate-pulse rounded-xl bg-muted" />
        <span className="h-72 w-full animate-pulse rounded-xl bg-muted" />
      </main>
    </div>
  )
}

function ProfileErrorPanel({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="min-h-dvh bg-background text-foreground">
      <ProductHeader active="players" />
      <main className="mx-auto flex w-full max-w-7xl flex-col gap-5 px-4 py-6 md:px-6 md:py-8">
        <Link href="/players" className={cn(buttonVariants({ variant: 'ghost', size: 'sm' }), 'w-fit')}>
          <ArrowLeft data-icon="inline-start" aria-hidden="true" />
          返回球员目录
        </Link>
        <div className="flex min-h-72 flex-col items-center justify-center gap-3 rounded-xl bg-card px-4 text-center ring-1 ring-foreground/10" role="alert">
          <span className="flex size-12 items-center justify-center rounded-full bg-destructive/10 text-destructive">
            <AlertTriangle aria-hidden="true" className="size-5" />
          </span>
          <div className="flex max-w-md flex-col gap-1">
            <p className="font-medium">球员资料加载失败</p>
            <p className="text-sm leading-relaxed text-muted-foreground">{message}</p>
          </div>
          <Button type="button" variant="outline" onClick={onRetry}>重试加载</Button>
        </div>
      </main>
    </div>
  )
}

function ProfileNotFoundPanel() {
  return (
    <div className="min-h-dvh bg-background text-foreground">
      <ProductHeader active="players" />
      <main className="mx-auto flex w-full max-w-7xl flex-col gap-5 px-4 py-6 md:px-6 md:py-8">
        <Link href="/players" className={cn(buttonVariants({ variant: 'ghost', size: 'sm' }), 'w-fit')}>
          <ArrowLeft data-icon="inline-start" aria-hidden="true" />
          返回球员目录
        </Link>
        <div className="flex min-h-72 flex-col items-center justify-center gap-3 rounded-xl bg-card px-4 text-center ring-1 ring-foreground/10">
          <div className="flex max-w-md flex-col gap-1">
            <p className="font-medium">未找到该球员</p>
            <p className="text-sm leading-relaxed text-muted-foreground">
              该内部球员 ID 没有对应的本地目录成员，请返回球员目录重新查找。
            </p>
          </div>
          <Link href="/players" className={cn(buttonVariants({ variant: 'outline' }))}>返回球员目录</Link>
        </div>
      </main>
    </div>
  )
}

/**
 * Production container for `/players/[playerId]`: consumes the versioned
 * REST profile/results APIs and renders the frozen v0 structure with real
 * loading / empty / partial / error / stale / not_found handling.
 */
export function PlayerProfileLive({ playerId }: { playerId: string }) {
  const [profile, setProfile] = useState<ProfileState>({ phase: 'loading' })
  const [results, setResults] = useState<ResultsState>({ phase: 'loading' })
  const [retryKey, setRetryKey] = useState(0)
  const [season, setSeason] = useState(() => new Date().getFullYear())
  const [tier, setTier] = useState<'ALL' | CompetitionTier>('ALL')
  const [outcome, setOutcome] = useState<'ALL' | MatchOutcome>('ALL')
  const [page, setPage] = useState(1)

  useEffect(() => {
    const controller = new AbortController()
    setProfile({ phase: 'loading' })
    getPlayerProfile(playerId, undefined, controller.signal)
      .then((view) => {
        if (controller.signal.aborted) return
        setProfile({ phase: 'ready', view })
        setSeason((current) => (current === view.selected_season ? current : view.selected_season))
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) return
        if (error instanceof ApiError && error.status === 404) {
          setProfile({ phase: 'not_found' })
          return
        }
        setProfile({
          phase: 'error',
          message: error instanceof ApiError && error.message ? error.message : '无法连接到球员资料服务，请稍后重试。',
        })
      })
    return () => controller.abort()
  }, [playerId, retryKey])

  useEffect(() => {
    const controller = new AbortController()
    setResults({ phase: 'loading' })
    getPlayerResults(
      playerId,
      {
        season,
        tiers: tier === 'ALL' ? [] : [viewTierToCircuitTier(tier)],
        outcome: outcomeParam(outcome),
        page,
      },
      controller.signal,
    )
      .then((resultPage) => {
        if (controller.signal.aborted) return
        setResults({ phase: 'ready', page: resultPage })
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) return
        if (error instanceof ApiError && error.status === 404 && profile.phase !== 'not_found') {
          setProfile({ phase: 'not_found' })
          return
        }
        setResults({ phase: 'error' })
      })
    return () => controller.abort()
    // `profile.phase` only guards the 404 cross-effect and must not refire fetches.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [playerId, season, tier, outcome, page, retryKey])

  if (profile.phase === 'loading') return <ProfilePageSkeleton />
  if (profile.phase === 'error') {
    return <ProfileErrorPanel message={profile.message} onRetry={() => setRetryKey((key) => key + 1)} />
  }
  if (profile.phase === 'not_found') return <ProfileNotFoundPanel />

  const view = profile.view
  const preview = toProfilePreview(view)
  const seasonRecord = view.profile.seasons.find((record) => record.season === season) ?? null
  const summary = toSeasonSummary(season, seasonRecord)
  const currentStatus = toCurrentStatus(view.current_match, view.profile.player.id)
  const seasons = view.profile.seasons.map((record) => record.season)

  const historyState: PlayerHistoryState =
    results.phase === 'loading'
      ? 'loading'
      : results.phase === 'error'
        ? 'error'
        : resultsHistoryState(results.page)
  const resultPreviews =
    results.phase === 'ready'
      ? results.page.matches.map((match) => toResultPreview(match, playerId, season))
      : []

  return (
    <div className="min-h-dvh bg-background text-foreground">
      <ProductHeader active="players" />
      <main className="mx-auto flex w-full max-w-7xl flex-col gap-5 px-4 py-6 md:px-6 md:py-8">
        <Link href="/players" className={cn(buttonVariants({ variant: 'ghost', size: 'sm' }), 'w-fit')}>
          <ArrowLeft data-icon="inline-start" aria-hidden="true" />
          返回球员目录
        </Link>

        <PlayerProfileHeader profile={preview} />

        <div className="grid gap-5 lg:grid-cols-[minmax(0,1.45fr)_minmax(20rem,0.75fr)]">
          <PlayerSeasonSummary summary={summary} />
          <PlayerCurrentStatus status={currentStatus} profileName={preview.name} />
        </div>

        <PlayerResults
          playerName={preview.name}
          playerTour={preview.tour}
          results={resultPreviews}
          historyState={historyState}
          season={season}
          onSeasonChange={(next) => { setSeason(next); setPage(1) }}
          onRetry={() => setRetryKey((key) => key + 1)}
          seasons={seasons.length ? seasons : undefined}
          tier={tier}
          onTierChange={(next) => { setTier(next); setPage(1) }}
          outcome={outcome}
          onOutcomeChange={(next) => { setOutcome(next); setPage(1) }}
          page={page}
          onPageChange={setPage}
          total={results.phase === 'ready' ? results.page.total : undefined}
        />
      </main>
    </div>
  )
}
