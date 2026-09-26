import Link from 'next/link'
import { useCallback, useEffect, useRef, useState } from 'react'
import { ArrowRight, CircleAlert, Radar, ShieldCheck } from 'lucide-react'

import { DecisionStatusBadge, decisionStateLabels } from '@/components/p3/decision-status'
import { PlayerAvatar } from '@/components/player-avatar'
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
import { ApiError, getMarketPulse } from '@/lib/api/client'
import { userFacingApiError } from '@/lib/api/user-facing-errors'
import { useMarketStream } from '@/hooks/use-market-stream'
import { selectHomePulseRows, toPulseRow, type PulseRowModel } from '@/lib/p3-view-models'
import { cn } from '@/lib/utils'

const REFRESH_DEBOUNCE_MS = 750

function formatPercent(value: number | null): string {
  if (value === null) return '—'
  return `${(value * 100).toFixed(1)}%`
}

function formatEdge(value: number | null): string {
  if (value === null) return '—'
  return `${value > 0 ? '+' : ''}${value.toFixed(1)} 个百分点`
}

type PulseStatus = 'probing' | 'ready' | 'empty' | 'error' | 'disabled'

/** Live Home Market Pulse: at most three rows, urgent position reserved,
 * whole-row internal navigation, no trajectories and no ledger detail. */
export function LiveMarketPulse({
  onAvailability,
}: {
  onAvailability?: (active: boolean) => void
}) {
  const [status, setStatus] = useState<PulseStatus>('probing')
  const [rows, setRows] = useState<PulseRowModel[]>([])
  const [errorCode, setErrorCode] = useState<string | null>(null)
  const mountedRef = useRef(true)
  mountedRef.current = true
  useEffect(() => () => { mountedRef.current = false }, [])
  const debounceRef = useRef<number | null>(null)
  useEffect(
    () => () => {
      if (debounceRef.current !== null) window.clearTimeout(debounceRef.current)
    },
    [],
  )

  const load = useCallback(async () => {
    try {
      const pulse = await getMarketPulse()
      if (!mountedRef.current) return
      const now = new Date()
      const mapped = selectHomePulseRows(pulse.data.map((row) => toPulseRow(row, now)))
      setRows(mapped)
      setErrorCode(null)
      setStatus(mapped.length === 0 ? 'empty' : 'ready')
      onAvailability?.(true)
    } catch (error) {
      if (!mountedRef.current) return
      if (error instanceof ApiError && error.code === 'p3_disabled') {
        setStatus('disabled')
        onAvailability?.(false)
        return
      }
      setErrorCode(
        error instanceof ApiError
          ? error.code
          : typeof error === 'object' && error !== null && 'code' in error
            ? String((error as { code: unknown }).code)
            : 'internal_error',
      )
      setStatus('error')
      // A transport failure is not a P3 absence: keep probing as available
      // only if rows were previously rendered; otherwise stay honest.
    }
  }, [onAvailability])

  useEffect(() => {
    void load()
  }, [load])

  const scheduleRefresh = useCallback(() => {
    if (debounceRef.current !== null) window.clearTimeout(debounceRef.current)
    debounceRef.current = window.setTimeout(() => {
      debounceRef.current = null
      void load()
    }, REFRESH_DEBOUNCE_MS)
  }, [load])

  const stream = useMarketStream({ onGap: scheduleRefresh })
  const firstRender = useRef(true)
  useEffect(() => {
    if (firstRender.current) {
      firstRender.current = false
      return
    }
    scheduleRefresh()
  }, [stream.books, stream.decisions, stream.paper, stream.resolutions, scheduleRefresh])

  if (status === 'probing' || status === 'disabled') return null

  const anyStale = rows.some((row) => row.stale)

  return (
    <section id="market-pulse" className="home-reveal flex scroll-mt-24 flex-col gap-4" aria-labelledby="market-pulse-title">
      <Card data-tone="market">
        <CardHeader className="border-b">
          <div className="flex items-center gap-2 text-primary">
            <Radar aria-hidden="true" className="size-4" />
            <CardTitle><h2 id="market-pulse-title">市场脉搏</h2></CardTitle>
          </div>
          <p className="text-sm text-muted-foreground">优先显示进行中的模拟记录，以及正在直播或即将开始的比赛。</p>
          <CardAction className="flex items-center gap-2">
            <Link href="/markets" className={cn(buttonVariants({ variant: 'outline', size: 'sm' }))}>
              查看全部
              <ArrowRight data-icon="inline-end" aria-hidden="true" />
            </Link>
          </CardAction>
        </CardHeader>

        <CardContent className="min-h-64 px-0">
          {status === 'error' ? (
            <div role="alert" className="mx-4 mb-3 flex items-start gap-2 rounded-lg border border-destructive/25 bg-destructive/8 p-3 text-sm text-destructive">
              <CircleAlert aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
              <span>{userFacingApiError(errorCode, 'market')}</span>
              <span>其他 Tennix 信息不受影响。</span>
              <button type="button" className="underline" onClick={() => void load()}>重试</button>
            </div>
          ) : null}

          {anyStale ? (
            <div role="status" className="mx-4 mb-3 flex items-start gap-2 rounded-lg border border-destructive/25 bg-destructive/8 p-3 text-sm text-destructive">
              <CircleAlert aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
              部分市场报价更新较慢，已暂停相关模拟操作；仍显示上次有效报价。
            </div>
          ) : null}

          {status === 'empty' ? (
            <div className="flex min-h-56 flex-col items-center justify-center gap-3 px-5 text-center">
              <div className="flex size-10 items-center justify-center rounded-lg bg-secondary text-primary">
                <Radar aria-hidden="true" className="size-5" />
              </div>
              <div>
                <p className="font-medium">暂无值得关注的市场机会</p>
                <p className="mt-1 max-w-md text-sm leading-relaxed text-muted-foreground">
                  市场会持续更新；没有合适机会时，不会硬凑结果。
                </p>
              </div>
            </div>
          ) : (
            <div className="divide-y">
              {rows.map((row) => (
                <Link
                  key={row.id}
                  href={row.href}
                  className="group grid min-h-24 grid-cols-2 gap-3 px-4 py-4 outline-none transition-colors hover:bg-muted/35 focus-visible:bg-muted/35 focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring sm:grid-cols-[minmax(16rem,1.6fr)_minmax(6rem,0.55fr)_minmax(8rem,0.7fr)_auto_auto] sm:items-center"
                  aria-label={`查看 ${row.match} 的${decisionStateLabels[row.state]}判断`}
                >
                  <div className="col-span-2 min-w-0 sm:col-span-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <div className="flex min-w-0 items-center gap-2">
                        <PlayerAvatar name={row.playerNames?.[0] ?? row.match} imageUrl={row.playerImages?.[0]} className="size-8" />
                        <p className="truncate font-semibold">{row.match}</p>
                        <PlayerAvatar name={row.playerNames?.[1] ?? row.match} imageUrl={row.playerImages?.[1]} className="size-8" />
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
                    <DecisionStatusBadge state={row.state} overlay={row.overlay} />
                    <span className="font-mono text-xs text-muted-foreground">{formatEdge(row.edgePp)}</span>
                  </div>
                  <div className="flex items-center justify-end gap-2 text-xs text-muted-foreground">
                    <span>{row.freshness}</span>
                    <ArrowRight aria-hidden="true" className="size-4 text-foreground transition-transform group-hover:translate-x-0.5" />
                  </div>
                </Link>
              ))}
            </div>
          )}
        </CardContent>

        <CardFooter className="items-start gap-3 text-xs leading-relaxed text-muted-foreground">
          <ShieldCheck aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-primary" />
          胜率由模型估算，价格来自实时市场；这里只记录模拟交易，不涉及真实资金。
        </CardFooter>
      </Card>
    </section>
  )
}
