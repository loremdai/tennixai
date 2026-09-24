import Link from 'next/link'
import { ArrowRight, FilterX, Landmark, RotateCcw } from 'lucide-react'

import { DecisionStatusBadge } from '@/components/p3/decision-status'
import {
  filterMarketListings,
  marketListingFixtures,
  type MarketGender,
  type MarketsPreviewState,
  type MatchPhase,
  type TourTier,
} from '@/components/p3/p3-preview-data'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { cn } from '@/lib/utils'

const tierOptions: Array<{ value: TourTier; label: string }> = [
  { value: 'main', label: 'ATP/WTA 主巡' },
  { value: 'challenger', label: '挑战赛' },
  { value: 'itf', label: 'ITF 巡回赛' },
  { value: 'other', label: '其他比赛' },
]

function formatPercent(value: number): string {
  return `${(value * 100).toFixed(1)}%`
}

function FilterChip({ active, children, onClick }: { active: boolean; children: React.ReactNode; onClick: () => void }) {
  return (
    <Button
      type="button"
      variant={active ? 'secondary' : 'outline'}
      size="lg"
      aria-pressed={active}
      onClick={onClick}
      className="h-11 md:h-9"
    >
      {children}
    </Button>
  )
}

export function AllMarketsView({
  state,
  tiers,
  gender,
  phase,
  onTiersChange,
  onGenderChange,
  onPhaseChange,
  onReset,
}: {
  state: MarketsPreviewState
  tiers: TourTier[]
  gender: MarketGender | 'all'
  phase: MatchPhase | 'all'
  onTiersChange: (tiers: TourTier[]) => void
  onGenderChange: (gender: MarketGender | 'all') => void
  onPhaseChange: (phase: MatchPhase | 'all') => void
  onReset: () => void
}) {
  const available = state === 'supplier_empty' ? [] : marketListingFixtures.map((item, index) => ({
    ...item,
    stale: state === 'partial_stale' && index === 2 ? true : item.stale,
    freshness: state === 'partial_stale' && index === 2 ? '上次有效报价 · 2 分 31 秒前' : item.freshness,
  }))
  const filtered = state === 'filtered_empty' ? [] : filterMarketListings(available, tiers, gender, phase)
  const hasFilters = tiers.length > 0 || gender !== 'all' || phase !== 'all'

  return (
    <section className="flex flex-col gap-4" aria-labelledby="all-markets-title">
      <div className="flex flex-col gap-3 rounded-xl border bg-card/65 p-4">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h2 id="all-markets-title" className="font-semibold">市场筛选</h2>
            <p className="mt-1 text-sm text-muted-foreground">可同时按赛事级别、组别和比赛状态筛选。</p>
          </div>
          {hasFilters ? (
            <Button variant="ghost" size="sm" onClick={onReset}>
              <RotateCcw data-icon="inline-start" aria-hidden="true" />
              重置
            </Button>
          ) : null}
        </div>

        <div className="flex flex-col gap-3">
          <fieldset>
            <legend className="mb-2 text-xs font-medium text-muted-foreground">赛事级别</legend>
            <div className="flex flex-wrap gap-2">
              {tierOptions.map((option) => (
                <FilterChip
                  key={option.value}
                  active={tiers.includes(option.value)}
                  onClick={() => onTiersChange(
                    tiers.includes(option.value)
                      ? tiers.filter((item) => item !== option.value)
                      : [...tiers, option.value],
                  )}
                >
                  {option.label}
                </FilterChip>
              ))}
            </div>
          </fieldset>
          <div className="grid gap-3 sm:grid-cols-2">
            <fieldset>
              <legend className="mb-2 text-xs font-medium text-muted-foreground">组别</legend>
              <div className="flex flex-wrap gap-2">
                {([['all', '全部'], ['men', '男子'], ['women', '女子']] as const).map(([value, label]) => (
                  <FilterChip key={value} active={gender === value} onClick={() => onGenderChange(value)}>{label}</FilterChip>
                ))}
              </div>
            </fieldset>
            <fieldset>
              <legend className="mb-2 text-xs font-medium text-muted-foreground">比赛阶段</legend>
              <div className="flex flex-wrap gap-2">
                {([['all', '全部'], ['live', '直播'], ['upcoming', '即将开始']] as const).map(([value, label]) => (
                  <FilterChip key={value} active={phase === value} onClick={() => onPhaseChange(value)}>{label}</FilterChip>
                ))}
              </div>
            </fieldset>
          </div>
        </div>
      </div>

      {filtered.length === 0 ? (
        <Card>
          <CardContent className="flex min-h-64 flex-col items-center justify-center gap-3 text-center">
            <div className="flex size-10 items-center justify-center rounded-lg bg-secondary text-primary">
              {state === 'supplier_empty' ? <Landmark aria-hidden="true" className="size-5" /> : <FilterX aria-hidden="true" className="size-5" />}
            </div>
            <div>
              <h3 className="font-semibold">{state === 'supplier_empty' ? '暂时没有市场报价' : '没有符合条件的比赛'}</h3>
              <p className="mt-1 max-w-md text-sm leading-relaxed text-muted-foreground">
                {state === 'supplier_empty'
                  ? '稍后再来看看，新的比赛和报价会持续更新。'
                  : '试着减少筛选条件，或重置筛选后查看全部比赛。'}
              </p>
            </div>
            {state !== 'supplier_empty' ? <Button variant="outline" onClick={onReset}>重置筛选</Button> : null}
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-3" aria-live="polite">
          {filtered.map((market) => (
            <Link
              key={market.id}
              href={market.href}
              className="group rounded-xl outline-none focus-visible:ring-2 focus-visible:ring-ring"
              aria-label={`查看 ${market.match} 市场`}
            >
              <Card size="sm" className="transition-[transform,box-shadow] group-hover:-translate-y-0.5 group-hover:ring-primary/35">
                <CardContent className="grid min-h-28 grid-cols-2 items-center gap-4 py-1 md:grid-cols-[minmax(15rem,1.5fr)_minmax(11rem,0.9fr)_minmax(8rem,0.65fr)_minmax(11rem,1fr)_auto]">
                  <div className="col-span-2 min-w-0 md:col-span-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <h3 className="truncate font-semibold">{market.match}</h3>
                      <Badge variant="outline">{market.phase === 'live' ? '直播' : '即将开始'}</Badge>
                      <Badge variant="secondary">{tierOptions.find((item) => item.value === market.tier)?.label}</Badge>
                    </div>
                    <p className="mt-1 truncate text-sm text-muted-foreground">{market.tournament}</p>
                    <p className="mt-2 text-xs text-muted-foreground">{market.reason}</p>
                  </div>

                  <dl className="grid grid-cols-2 gap-3 rounded-lg bg-muted/30 p-3">
                    <div>
                      <dt className="truncate text-xs text-muted-foreground">{market.playerOne} 买入价</dt>
                      <dd className="mt-1 font-mono text-lg font-semibold tabular-nums">{formatPercent(market.playerOneAsk)}</dd>
                    </div>
                    <div>
                      <dt className="truncate text-xs text-muted-foreground">{market.playerTwo} 买入价</dt>
                      <dd className="mt-1 font-mono text-lg font-semibold tabular-nums">{formatPercent(market.playerTwoAsk)}</dd>
                    </div>
                  </dl>

                  <dl>
                    <dt className="text-xs text-muted-foreground">模型估算胜率</dt>
                    <dd className="mt-1 font-mono text-lg font-semibold tabular-nums">{market.modelProbability === null ? '—' : formatPercent(market.modelProbability)}</dd>
                    <dd className="mt-1 text-xs text-muted-foreground">{market.covered ? '模型已提供估算' : '暂不提供胜率估算'}</dd>
                  </dl>

                  <dl className="grid grid-cols-2 gap-3">
                    <div><dt className="text-xs text-muted-foreground">买卖价差</dt><dd className="mt-1 font-mono font-semibold">{formatPercent(market.spread)}</dd></div>
                    <div><dt className="text-xs text-muted-foreground">可交易金额</dt><dd className="mt-1 font-mono font-semibold">${market.depth}</dd></div>
                    <div className="col-span-2"><dt className="sr-only">报价更新时间</dt><dd className={cn('text-xs text-muted-foreground', market.stale && 'text-destructive')}>{market.freshness}</dd></div>
                  </dl>

                  <div className="flex items-center justify-between gap-2 md:justify-end">
                    <DecisionStatusBadge state={market.state} overlay={market.stale ? 'stale' : 'none'} />
                    <ArrowRight aria-hidden="true" className="size-4 shrink-0 text-foreground transition-transform group-hover:translate-x-0.5" />
                  </div>
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </section>
  )
}
