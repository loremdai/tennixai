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
  market_only: 'MARKET ONLY',
  no_bet: 'NO BET',
  wait: 'WAIT',
  buy: 'BUY',
  entry_pending: 'ENTRY PENDING',
  missed: 'MISSED',
  hold: 'FILLED / HOLD',
  sell: 'SELL',
  exit_pending: 'EXIT PENDING',
  exited: 'EXITED',
  exit_missed: 'EXIT MISSED',
  settled: 'SETTLED',
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
          STALE
        </Badge>
      ) : overlay === 'gap' ? (
        <Badge variant="destructive">
          <CircleDashed data-icon="inline-start" aria-hidden="true" />
          DATA GAP
        </Badge>
      ) : null}
    </span>
  )
}

export { stateLabels as decisionStateLabels }
