import Link from 'next/link'
import { ArrowRight } from 'lucide-react'

import { DecisionStatusBadge } from '@/components/p3/decision-status'
import { PlayerAvatar } from '@/components/player-avatar'
import { PlayerName } from '@/components/player-name'
import { Card, CardContent } from '@/components/ui/card'
import { cn } from '@/lib/utils'

export type PaperRowData = {
  id: string
  match: string
  tournament: string
  direction: string
  directionLocalizedName?: string | null
  playerNames?: [string, string] | null
  playerLocalizedNames?: [string | null, string | null] | null
  playerImages?: [string | null, string | null] | null
  state: 'entry_pending' | 'hold' | 'exit_pending' | 'exit_missed' | 'exited' | 'missed' | 'settled'
  cost: number
  shares: number
  averageEntry: number | null
  currentExitValue: number | null
  netPnl: number | null
  freshness: string
  detail: string
  href: string
}

function money(value: number | null): string {
  if (value === null) return '—'
  return `${value < 0 ? '-' : ''}$${Math.abs(value).toFixed(2)}`
}

export function PaperRow({ record }: { record: PaperRowData }) {
  const entryPending = record.state === 'entry_pending'
  const noPosition = entryPending || record.state === 'missed'
  const amountLabel = entryPending
    ? '计划投入 / 报价均价'
    : '模拟投入 / 买入均价'
  const averageEntry = record.averageEntry === null
    ? '—'
    : `${(record.averageEntry * 100).toFixed(1)}%`
  const formattedAmount = `${money(record.cost)} · ${averageEntry}`
  const amountValue = noPosition && !entryPending ? '— · —' : formattedAmount
  const sharesLabel = entryPending ? '预计份额' : '持有份额'
  const sharesValue = noPosition && !entryPending ? '—' : record.shares.toFixed(2)

  return (
    <Link
      href={record.href}
      className="group rounded-xl outline-none focus-visible:ring-2 focus-visible:ring-ring"
      aria-label={`查看 ${record.match} 的模拟记录`}
    >
      <Card size="sm" className="transition-[transform,box-shadow] group-hover:-translate-y-0.5 group-hover:ring-primary/35">
        <CardContent className="grid min-h-28 grid-cols-2 items-center gap-4 py-1 md:grid-cols-[minmax(15rem,1.5fr)_minmax(8rem,0.7fr)_minmax(7rem,0.55fr)_minmax(8rem,0.65fr)_minmax(7rem,0.55fr)_auto_auto]">
          <div className="col-span-2 min-w-0 md:col-span-1">
            <div className="flex min-w-0 items-center gap-2">
              <PlayerAvatar name={record.playerNames?.[0] ?? record.match} imageUrl={record.playerImages?.[0]} className="size-8" />
              <h3 className="flex min-w-0 items-center gap-1 font-semibold">
                {record.playerNames ? (
                  <>
                    <PlayerName name={record.playerNames[0]} localizedName={record.playerLocalizedNames?.[0]} className="min-w-0" />
                    <span className="shrink-0 text-xs text-muted-foreground">vs.</span>
                    <PlayerName name={record.playerNames[1]} localizedName={record.playerLocalizedNames?.[1]} className="min-w-0" />
                  </>
                ) : record.match}
              </h3>
              <PlayerAvatar name={record.playerNames?.[1] ?? record.match} imageUrl={record.playerImages?.[1]} className="size-8" />
            </div>
            <p className="mt-1 truncate text-sm text-muted-foreground">{record.tournament}</p>
            <p className="mt-2 flex items-center gap-1 text-xs font-medium text-primary">
              <span>方向：</span>
              <PlayerName name={record.direction} localizedName={record.directionLocalizedName} />
            </p>
          </div>
          <dl><dt className="text-xs text-muted-foreground">{amountLabel}</dt><dd className="mt-1 font-mono font-semibold">{amountValue}</dd></dl>
          <dl><dt className="text-xs text-muted-foreground">{sharesLabel}</dt><dd className="mt-1 font-mono text-lg font-semibold tabular-nums">{sharesValue}</dd></dl>
          <dl><dt className="text-xs text-muted-foreground">退出参考金额</dt><dd className="mt-1 font-mono text-lg font-semibold tabular-nums">{money(record.currentExitValue)}</dd>{record.currentExitValue !== null ? <dd className="mt-1 max-w-48 text-xs leading-relaxed text-muted-foreground">按当前最高买价估算，未扣费用，也不保证全部份额都能按此价格卖出。</dd> : null}</dl>
          <dl>
            <dt className="text-xs text-muted-foreground">模拟盈亏</dt>
            <dd className={cn(
              'mt-1 font-mono text-lg font-semibold tabular-nums',
              !noPosition && record.netPnl !== null && record.netPnl > 0 && 'text-primary',
              !noPosition && record.netPnl !== null && record.netPnl < 0 && 'text-destructive',
              noPosition || record.netPnl === null ? 'text-muted-foreground' : '',
            )}>{noPosition || record.netPnl === null ? '—' : `${record.netPnl > 0 ? '+' : ''}${money(record.netPnl)}`}</dd>
          </dl>
          <div className="flex flex-col items-start gap-1">
            <DecisionStatusBadge state={record.state} />
            <span className="max-w-48 text-xs leading-relaxed text-muted-foreground">{record.detail}</span>
          </div>
          <div className="flex items-center justify-end gap-2 text-xs text-muted-foreground">
            <span>{record.freshness}</span>
            <ArrowRight aria-hidden="true" className="size-4 text-foreground transition-transform group-hover:translate-x-0.5" />
          </div>
        </CardContent>
      </Card>
    </Link>
  )
}
