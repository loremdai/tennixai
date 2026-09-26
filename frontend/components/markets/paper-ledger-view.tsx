import Link from 'next/link'
import { ArrowRight, BookOpenCheck, ShieldCheck } from 'lucide-react'

import { DecisionStatusBadge } from '@/components/p3/decision-status'
import { PlayerAvatar } from '@/components/player-avatar'
import { PlayerName } from '@/components/player-name'
import {
  openPaperFixtures,
  terminalPaperFixtures,
  splitPreviewMatchPlayers,
  type MarketsPreviewState,
  type PaperLedgerPreview,
} from '@/components/p3/p3-preview-data'
import { Card, CardContent } from '@/components/ui/card'
import { cn } from '@/lib/utils'

function money(value: number | null): string {
  if (value === null) return '—'
  return `${value < 0 ? '-' : ''}$${Math.abs(value).toFixed(2)}`
}

const paperPriority: Record<PaperLedgerPreview['state'], number> = {
  hold: 0,
  exit_pending: 1,
  entry_pending: 2,
  exited: 3,
  missed: 4,
  settled: 5,
}

export function PaperLedgerView({ state }: { state: MarketsPreviewState }) {
  let records: PaperLedgerPreview[]
  if (state === 'empty') {
    records = []
  } else if (state === 'terminal') {
    records = terminalPaperFixtures
  } else if (state === 'resolution_pending') {
    records = [openPaperFixtures[2], openPaperFixtures[0]]
  } else {
    records = openPaperFixtures
  }
  records = [...records].sort((a, b) => paperPriority[a.state] - paperPriority[b.state])

  if (records.length === 0) {
    return (
      <Card>
        <CardContent className="flex min-h-72 flex-col items-center justify-center gap-3 text-center">
          <div className="flex size-10 items-center justify-center rounded-lg bg-secondary text-primary">
            <BookOpenCheck aria-hidden="true" className="size-5" />
          </div>
          <div>
            <h2 className="font-semibold">暂无模拟记录</h2>
            <p className="mt-1 max-w-md text-sm leading-relaxed text-muted-foreground">
              符合条件的模拟记录会显示在这里；不涉及真实资金。
            </p>
          </div>
        </CardContent>
      </Card>
    )
  }

  return (
    <section className="flex flex-col gap-3" aria-labelledby="paper-ledger-title">
      <div className="flex items-end justify-between gap-3">
        <div>
          <h2 id="paper-ledger-title" className="text-lg font-semibold">模拟记录</h2>
          <p className="mt-1 text-sm text-muted-foreground">查看模拟投入、当前价值和盈亏变化。</p>
        </div>
        <span className="font-mono text-xs text-muted-foreground">{records.length} 条</span>
      </div>

      <div className="grid gap-3">
        {records.map((record) => {
          const [playerOne, playerTwo] = splitPreviewMatchPlayers(record.match)
          const entryPending = record.state === 'entry_pending'
          const noPosition = entryPending || record.state === 'missed'
          const averageEntry = `${(record.averageEntry * 100).toFixed(1)}%`
          const amount = noPosition && !entryPending
            ? '— · —'
            : `${money(record.cost)} · ${averageEntry}`

          return (
            <Link
              key={record.id}
              href={record.href}
              className="group rounded-xl outline-none focus-visible:ring-2 focus-visible:ring-ring"
              aria-label={`查看 ${record.match} 的模拟记录`}
            >
              <Card size="sm" className="transition-[transform,box-shadow] group-hover:-translate-y-0.5 group-hover:ring-primary/35">
                <CardContent className="grid min-h-28 grid-cols-2 items-center gap-4 py-1 md:grid-cols-[minmax(15rem,1.5fr)_minmax(8rem,0.7fr)_minmax(7rem,0.55fr)_minmax(8rem,0.65fr)_minmax(7rem,0.55fr)_auto_auto]">
                  <div className="col-span-2 min-w-0 md:col-span-1">
                    <div className="flex min-w-0 items-center gap-2">
                      <PlayerAvatar name={playerOne} className="size-7" />
                      <h3 className="flex min-w-0 items-center gap-1 font-semibold">
                        <PlayerName name={playerOne} localizedName={record.playerLocalizedNames?.[0]} className="min-w-0" />
                        <span className="shrink-0 text-xs text-muted-foreground">vs.</span>
                        <PlayerName name={playerTwo} localizedName={record.playerLocalizedNames?.[1]} className="min-w-0" />
                      </h3>
                      <PlayerAvatar name={playerTwo} className="size-7" />
                    </div>
                    <p className="mt-1 truncate text-sm text-muted-foreground">{record.tournament}</p>
                    <p className="mt-2 flex items-center gap-1 text-xs font-medium text-primary">
                      <span>方向：</span>
                      <PlayerName name={record.direction} localizedName={record.directionLocalizedName} />
                      <span>胜出</span>
                    </p>
                  </div>
                  <dl>
                    <dt className="text-xs text-muted-foreground">
                      {entryPending ? '计划投入 / 报价均价' : '模拟投入 / 买入均价'}
                    </dt>
                    <dd className="mt-1 font-mono font-semibold">{amount}</dd>
                  </dl>
                  <dl>
                    <dt className="text-xs text-muted-foreground">
                      {entryPending ? '预计份额' : '持有份额'}
                    </dt>
                    <dd className="mt-1 font-mono text-lg font-semibold tabular-nums">
                      {noPosition ? '—' : record.shares.toFixed(2)}
                    </dd>
                  </dl>
                  <dl>
                    <dt className="text-xs text-muted-foreground">退出参考金额</dt>
                    <dd className="mt-1 font-mono text-lg font-semibold tabular-nums">
                      {money(record.currentExitValue)}
                    </dd>
                    {record.currentExitValue !== null ? (
                      <dd className="mt-1 max-w-48 text-xs leading-relaxed text-muted-foreground">
                        按当前最高买价估算，未扣费用，也不保证全部份额都能按此价格卖出。
                      </dd>
                    ) : null}
                  </dl>
                  <dl>
                    <dt className="text-xs text-muted-foreground">模拟盈亏</dt>
                    <dd className={cn(
                      'mt-1 font-mono text-lg font-semibold tabular-nums',
                      !noPosition && record.netPnl !== null && record.netPnl > 0 && 'text-primary',
                      !noPosition && record.netPnl !== null && record.netPnl < 0 && 'text-destructive',
                      noPosition || record.netPnl === null ? 'text-muted-foreground' : '',
                    )}>
                      {noPosition || record.netPnl === null
                        ? '—'
                        : `${record.netPnl > 0 ? '+' : ''}${money(record.netPnl)}`}
                    </dd>
                  </dl>
                  <div className="flex flex-col items-start gap-1">
                    <DecisionStatusBadge state={record.state} />
                    <span className="max-w-48 text-xs leading-relaxed text-muted-foreground">
                      {record.detail}
                    </span>
                  </div>
                  <div className="flex items-center justify-end gap-2 text-xs text-muted-foreground">
                    <span>{record.freshness}</span>
                    <ArrowRight aria-hidden="true" className="size-4 text-foreground transition-transform group-hover:translate-x-0.5" />
                  </div>
                </CardContent>
              </Card>
            </Link>
          )
        })}
      </div>

      <div className="flex items-start gap-2 rounded-lg bg-muted/25 p-3 text-xs leading-relaxed text-muted-foreground">
        <ShieldCheck aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-primary" />
        模拟结果不代表真实收益，也不会涉及真实资金。
      </div>
    </section>
  )
}
