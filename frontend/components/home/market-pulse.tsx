'use client'

import { useState } from 'react'
import Link from 'next/link'
import { ArrowRight, CircleAlert, Radar, ShieldCheck } from 'lucide-react'

import { DecisionStatusBadge } from '@/components/p3/decision-status'
import { PlayerAvatar } from '@/components/player-avatar'
import { PlayerName } from '@/components/player-name'
import { P3PreviewControls } from '@/components/p3/p3-preview-controls'
import {
  getHomePulseRows,
  splitPreviewMatchPlayers,
  type HomePulseState,
} from '@/components/p3/p3-preview-data'
import { Badge } from '@/components/ui/badge'
import {
  Card,
  CardAction,
  CardContent,
  CardFooter,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { buttonVariants } from '@/components/ui/button'
import { cn } from '@/lib/utils'

function formatPercent(value: number): string {
  return `${(value * 100).toFixed(1)}%`
}

function formatEdge(value: number): string {
  return `${value > 0 ? '+' : ''}${value.toFixed(1)} 个百分点`
}

export function MarketPulse({ initialState }: { initialState: HomePulseState }) {
  const [state, setState] = useState(initialState)
  const rows = getHomePulseRows(state)

  function changeState(_: string, value: string) {
    const nextState = value as HomePulseState
    setState(nextState)
    const url = new URL(window.location.href)
    url.searchParams.set('preview', 'p3')
    url.searchParams.set('pulse', nextState)
    window.history.replaceState(null, '', url)
  }

  return (
    <section id="market-pulse" className="home-reveal flex scroll-mt-24 flex-col gap-4" aria-labelledby="market-pulse-title">
      <P3PreviewControls
        title="首页市场展示演示"
        description="切换不同状态，预览首页市场信息的展示方式。"
        fields={[
          {
            key: 'pulse',
            label: '页面状态',
            value: state,
            options: [
              { value: 'populated', label: '有机会' },
              { value: 'stale', label: '报价更新较慢' },
              { value: 'empty', label: '暂无机会' },
            ],
          },
        ]}
        onChange={changeState}
      />

      <Card data-tone="market">
        <CardHeader className="border-b">
          <div className="flex items-center gap-2 text-primary">
            <Radar aria-hidden="true" className="size-4" />
            <CardTitle><h2 id="market-pulse-title">市场脉搏</h2></CardTitle>
          </div>
          <p className="text-sm text-muted-foreground">优先显示进行中的模拟记录，以及值得关注的比赛。</p>
          <CardAction className="flex items-center gap-2">
            <Badge data-tone="beta" variant="outline">BETA</Badge>
            <Link href="/markets?preview=p3" className={cn(buttonVariants({ variant: 'outline', size: 'sm' }))}>
              查看全部
              <ArrowRight data-icon="inline-end" aria-hidden="true" />
            </Link>
          </CardAction>
        </CardHeader>

        <CardContent className="min-h-64 px-0">
          {state === 'stale' ? (
            <div role="status" className="mx-4 mb-3 flex items-start gap-2 rounded-lg border border-destructive/25 bg-destructive/8 p-3 text-sm text-destructive">
              <CircleAlert aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
              部分市场报价更新较慢，已暂停相关模拟操作；仍显示上次有效报价。
            </div>
          ) : null}

          {rows.length === 0 ? (
            <div className="flex min-h-56 flex-col items-center justify-center gap-3 px-5 text-center">
              <div className="flex size-10 items-center justify-center rounded-lg bg-secondary text-primary">
                <Radar aria-hidden="true" className="size-5" />
              </div>
              <div>
                <p className="font-medium">暂无符合门槛的市场机会</p>
                <p className="mt-1 max-w-md text-sm leading-relaxed text-muted-foreground">
                  市场仍在监测中；没有机会时不会用弱信号填满列表。
                </p>
              </div>
            </div>
          ) : (
            <div className="divide-y">
              {rows.map((row) => {
                const [playerOne, playerTwo] = splitPreviewMatchPlayers(row.match)
                return (
                  <Link
                    key={row.id}
                    href={row.href}
                    className="group grid min-h-24 grid-cols-2 gap-3 px-4 py-4 outline-none transition-colors hover:bg-muted/35 focus-visible:bg-muted/35 focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring sm:grid-cols-[minmax(16rem,1.6fr)_minmax(6rem,0.55fr)_minmax(8rem,0.7fr)_auto_auto] sm:items-center"
                    aria-label={`查看 ${row.match} 的 ${row.state} 决策`}
                  >
                    <div className="col-span-2 min-w-0 sm:col-span-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <div className="flex min-w-0 items-center gap-2">
                          <PlayerAvatar name={playerOne} className="size-8" />
                          <PlayerName name={playerOne} localizedName={row.playerLocalizedNames?.[0]} className="min-w-0 font-semibold" />
                          <span className="shrink-0 text-xs text-muted-foreground">vs.</span>
                          <PlayerName name={playerTwo} localizedName={row.playerLocalizedNames?.[1]} className="min-w-0 font-semibold" />
                          <PlayerAvatar name={playerTwo} className="size-8" />
                        </div>
                        <Badge variant="outline">{row.phase}</Badge>
                      </div>
                      <p className="mt-1 truncate text-xs text-muted-foreground">{row.tournament}</p>
                    </div>
                    <div>
                      <p className="text-xs text-muted-foreground">模型估算胜率</p>
                      <p className="mt-1 font-mono text-lg font-semibold tabular-nums">{formatPercent(row.modelProbability)}</p>
                    </div>
                    <div>
                      <p
                        className="text-xs text-muted-foreground"
                        title={row.priority === 'position' || row.priority === 'sell'
                          ? '按当前最高买价估算；不代表整笔持仓都能按此价格退出。'
                          : undefined}
                      >
                        {row.priority === 'position' || row.priority === 'sell'
                          ? '当前退出参考价'
                          : '10 美元模拟买入价'}
                      </p>
                      <p className="mt-1 font-mono text-lg font-semibold tabular-nums">{formatPercent(row.executableProbability)}</p>
                    </div>
                    <div className="flex flex-col items-start gap-1">
                      <DecisionStatusBadge state={row.state} overlay={row.stale ? 'stale' : 'none'} />
                      <span className="font-mono text-xs text-muted-foreground">{formatEdge(row.edgePp)}</span>
                    </div>
                    <div className="flex items-center justify-end gap-2 text-xs text-muted-foreground">
                      <span>{row.freshness}</span>
                      <ArrowRight aria-hidden="true" className="size-4 text-foreground transition-transform group-hover:translate-x-0.5" />
                    </div>
                  </Link>
                )
              })}
            </div>
          )}
        </CardContent>

        <CardFooter className="items-start gap-3 text-xs leading-relaxed text-muted-foreground">
          <ShieldCheck aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-primary" />
          仅用于比赛研究和模拟记录，不涉及真实资金。
        </CardFooter>
      </Card>
    </section>
  )
}
