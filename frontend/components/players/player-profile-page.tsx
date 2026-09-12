'use client'

import { useMemo, useState } from 'react'
import Link from 'next/link'
import { ArrowLeft, Check, ChevronDown, FlaskConical } from 'lucide-react'

import { ProductHeader } from '@/components/match/match-header'
import { PlayerCurrentStatus } from '@/components/players/player-current-status'
import {
  currentStatusFor,
  type PlayerHistoryState,
  type PlayerProfileBundle,
  type ProfileStatusKey,
} from '@/components/players/player-preview-data'
import { PlayerProfileHeader } from '@/components/players/player-profile-header'
import { PlayerResults } from '@/components/players/player-results'
import { PlayerSeasonSummary } from '@/components/players/player-season-summary'
import { Badge } from '@/components/ui/badge'
import { Button, buttonVariants } from '@/components/ui/button'
import {
  Card,
  CardAction,
  CardContent,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { cn } from '@/lib/utils'

const historyLabels: Record<PlayerHistoryState, string> = {
  ready: '完整赛果',
  empty: '空状态',
  partial: '部分数据',
  unavailable: '历史不可用',
  loading: '加载中',
  error: '加载失败',
  stale: '旧快照',
}

const statusLabels: Record<ProfileStatusKey, string> = {
  live: 'LIVE',
  next: '下一场',
  none: '暂无比赛',
}

function profileControlLabel(playerId: string, name: string) {
  if (playerId === 'plr_atp_ben_shelton') return '有头像档案'
  if (playerId === 'plr_wta_qinwen_zheng') return 'WTA 档案'
  if (playerId === 'plr_atp_bryan_shelton') return '资料缺失'
  return name
}

export function PlayerProfilePage({
  bundle,
  initialStatus,
  initialHistoryState,
}: {
  bundle: PlayerProfileBundle
  initialStatus: ProfileStatusKey
  initialHistoryState: PlayerHistoryState
}) {
  const [selectedPlayerId, setSelectedPlayerId] = useState(bundle.currentPlayerId)
  const [statusKey, setStatusKey] = useState(initialStatus)
  const [historyState, setHistoryState] = useState(initialHistoryState)
  const [season, setSeason] = useState(2026)

  const scenario = useMemo(
    () => bundle.scenarios.find((item) => item.profile.id === selectedPlayerId) ?? bundle.scenarios[0],
    [bundle.scenarios, selectedPlayerId],
  )
  const summary = scenario.seasonSummaries.find((item) => item.season === season) ?? scenario.seasonSummaries[0]
  const currentStatus = currentStatusFor(scenario.profile, statusKey)

  function selectProfile(playerId: string) {
    const nextScenario = bundle.scenarios.find((item) => item.profile.id === playerId)
    if (!nextScenario) return
    setSelectedPlayerId(playerId)
    setStatusKey(nextScenario.defaultStatus)
    setHistoryState(nextScenario.defaultHistoryState)
    setSeason(2026)
    window.history.replaceState(null, '', `/players/${playerId}`)
  }

  return (
    <div className="min-h-dvh bg-background text-foreground">
      <ProductHeader active="players" />
      <main className="mx-auto flex w-full max-w-7xl flex-col gap-5 px-4 py-6 md:px-6 md:py-8">
        <Link href="/players" className={cn(buttonVariants({ variant: 'ghost', size: 'sm' }), 'w-fit')}>
          <ArrowLeft data-icon="inline-start" aria-hidden="true" />
          返回球员目录
        </Link>

        <Card size="sm" className="bg-secondary/45" aria-labelledby="profile-preview-controls-title">
          <CardHeader>
            <div>
              <CardTitle>
                <h2 id="profile-preview-controls-title" className="inline-flex items-center gap-2">
                  <FlaskConical aria-hidden="true" className="size-4 text-primary" />
                  原型状态切换
                </h2>
              </CardTitle>
              <p className="mt-1 text-xs leading-relaxed text-muted-foreground">仅切换确定性 preview 数据，不请求生产 API。</p>
            </div>
            <CardAction><Badge variant="outline">PREVIEW</Badge></CardAction>
          </CardHeader>
          <CardContent className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
            <div className="flex flex-wrap items-center gap-2" aria-label="球员资料状态">
              <span className="text-xs text-muted-foreground">档案</span>
              {bundle.scenarios.map((item) => (
                <Button
                  key={item.profile.id}
                  type="button"
                  variant={item.profile.id === selectedPlayerId ? 'default' : 'outline'}
                  size="sm"
                  aria-pressed={item.profile.id === selectedPlayerId}
                  onClick={() => selectProfile(item.profile.id)}
                >
                  {profileControlLabel(item.profile.id, item.profile.name)}
                </Button>
              ))}
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <div className="flex flex-wrap items-center gap-2" aria-label="当前比赛状态">
                <span className="text-xs text-muted-foreground">当前状态</span>
                {(['live', 'next', 'none'] as const).map((status) => (
                  <Button
                    key={status}
                    type="button"
                    variant={statusKey === status ? 'default' : 'outline'}
                    size="sm"
                    aria-pressed={statusKey === status}
                    onClick={() => setStatusKey(status)}
                  >
                    {statusLabels[status]}
                  </Button>
                ))}
              </div>
              <DropdownMenu>
                <DropdownMenuTrigger render={<Button variant="outline" size="sm" aria-label="切换历史赛果可用性" />}>
                  {historyLabels[historyState]}
                  <ChevronDown data-icon="inline-end" aria-hidden="true" />
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" className="min-w-44">
                  <DropdownMenuGroup>
                    <DropdownMenuLabel>历史赛果状态</DropdownMenuLabel>
                    {(Object.keys(historyLabels) as PlayerHistoryState[]).map((state) => (
                      <DropdownMenuItem key={state} onClick={() => setHistoryState(state)}>
                        <span className="flex size-4 items-center justify-center">
                          {historyState === state ? <Check aria-hidden="true" /> : null}
                        </span>
                        {historyLabels[state]}
                      </DropdownMenuItem>
                    ))}
                  </DropdownMenuGroup>
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
          </CardContent>
        </Card>

        <PlayerProfileHeader key={`${scenario.profile.id}-profile`} profile={scenario.profile} />

        <div className="grid gap-5 lg:grid-cols-[minmax(0,1.45fr)_minmax(20rem,0.75fr)]">
          <PlayerSeasonSummary summary={summary} />
          <PlayerCurrentStatus status={currentStatus} profileName={scenario.profile.name} />
        </div>

        <PlayerResults
          key={`${scenario.profile.id}-results`}
          playerName={scenario.profile.name}
          playerTour={scenario.profile.tour}
          results={scenario.results}
          historyState={historyState}
          season={season}
          onSeasonChange={setSeason}
          onRetry={() => setHistoryState('ready')}
        />
      </main>
    </div>
  )
}
