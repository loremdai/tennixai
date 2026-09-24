import type { LucideIcon } from 'lucide-react'
import {
  Ban,
  CircleCheck,
  CircleDashed,
  CircleOff,
  Clock3,
  Eye,
  Hourglass,
  ShieldCheck,
  TrendingDown,
  TrendingUp,
  Trophy,
} from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import type { DecisionOverlay, DecisionState, DecisionTone } from '@/components/p3/p3-preview-data'
import { cn } from '@/lib/utils'

const stateIcons: Record<DecisionState, LucideIcon> = {
  market_only: Eye,
  no_bet: Ban,
  wait: Clock3,
  buy: TrendingUp,
  entry_pending: Hourglass,
  missed: CircleOff,
  hold: ShieldCheck,
  sell: TrendingDown,
  exit_pending: Hourglass,
  exited: CircleCheck,
  exit_missed: CircleOff,
  settled: Trophy,
}

const stateLabels: Record<DecisionState, string> = {
  market_only: '仅显示市场报价',
  no_bet: '暂不参与',
  wait: '等待更好价格',
  buy: '模拟买入机会',
  entry_pending: '等待买入确认',
  missed: '未模拟买入',
  hold: '模拟持有中',
  sell: '模拟退出机会',
  exit_pending: '等待退出确认',
  exited: '已模拟退出',
  exit_missed: '退出未成交',
  settled: '已结算',
}

const stateTones: Record<DecisionState, DecisionTone> = {
  market_only: 'neutral',
  no_bet: 'neutral',
  wait: 'pending',
  buy: 'positive',
  entry_pending: 'pending',
  missed: 'negative',
  hold: 'positive',
  sell: 'negative',
  exit_pending: 'pending',
  exited: 'neutral',
  exit_missed: 'negative',
  settled: 'neutral',
}

const toneClasses: Record<DecisionTone, string> = {
  positive: 'border-primary/25 bg-primary/12 text-primary',
  pending: 'border-chart-3/30 bg-chart-3/12 text-chart-3',
  neutral: 'border-border bg-muted/45 text-foreground',
  negative: 'border-destructive/25 bg-destructive/10 text-destructive',
}

export function DecisionStatusBadge({
  state,
  overlay = 'none',
  className,
}: {
  state: DecisionState
  overlay?: DecisionOverlay
  className?: string
}) {
  const Icon = stateIcons[state]
  const tone = stateTones[state]

  return (
    <span className={cn('inline-flex flex-wrap items-center gap-1.5', className)}>
      <Badge variant="outline" className={toneClasses[tone]}>
        <Icon data-icon="inline-start" aria-hidden="true" />
        {stateLabels[state]}
      </Badge>
      {overlay === 'stale' ? (
        <Badge variant="destructive">
          <Clock3 data-icon="inline-start" aria-hidden="true" />
          报价更新较慢
        </Badge>
      ) : overlay === 'gap' ? (
        <Badge variant="destructive">
          <CircleDashed data-icon="inline-start" aria-hidden="true" />
          比赛数据更新中断
        </Badge>
      ) : null}
    </span>
  )
}

export { stateLabels as decisionStateLabels }
