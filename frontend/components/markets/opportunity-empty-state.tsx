import { Radar } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import type { OpportunityAvailabilityReason } from '@/lib/api/types'

/**
 * Why the opportunities tab is empty, in the user's words. The server sends a
 * stable reason code and the page owns the copy; an unpromoted model must
 * explain itself instead of looking like a fault or hiding the tab.
 */
export const OPPORTUNITY_EMPTY_STATES: Record<
  OpportunityAvailabilityReason,
  { title: string; body: string; offersAllMarkets: boolean }
> = {
  HAS_OPPORTUNITIES: {
    title: '暂时没有可关注的机会',
    body: '目前没有比赛同时满足模型判断和报价条件。你可以先查看所有市场的最新报价。',
    offersAllMarkets: true,
  },
  ELIGIBLE_UNPROMOTED: {
    title: '模型仍在验证中',
    body: '模型验证尚未完成，因此暂不提供比赛判断；你仍可查看所有市场的最新报价。',
    offersAllMarkets: true,
  },
  NO_ELIGIBLE_ACTION: {
    title: '暂时没有可关注的机会',
    body: '目前没有符合条件的比赛。',
    offersAllMarkets: true,
  },
  NO_COVERED_MARKET: {
    title: '暂无可分析的比赛',
    body: '目前没有纳入分析的单打比赛；其他比赛的市场报价仍可查看。',
    offersAllMarkets: true,
  },
  DECISION_GAP: {
    title: '比赛数据暂时中断',
    body: '我们已暂停提供新的比赛判断，请稍后再试。',
    offersAllMarkets: true,
  },
}

export function OpportunityEmptyState({
  reason,
  onViewAllMarkets,
}: {
  /** Server-provided reason; null on older payloads falls back to neutral copy. */
  reason: OpportunityAvailabilityReason | null
  onViewAllMarkets: () => void
}) {
  const copy = OPPORTUNITY_EMPTY_STATES[reason ?? 'HAS_OPPORTUNITIES']
  return (
    <Card>
      <CardContent className="flex min-h-72 flex-col items-center justify-center gap-3 text-center">
        <div className="flex size-10 items-center justify-center rounded-lg bg-secondary text-primary">
          <Radar aria-hidden="true" className="size-5" />
        </div>
        <div>
          <h2 className="font-semibold">{copy.title}</h2>
          <p className="mt-1 max-w-md text-sm leading-relaxed text-muted-foreground">
            {copy.body}
          </p>
        </div>
        {copy.offersAllMarkets ? (
          <Button variant="outline" onClick={onViewAllMarkets}>
            查看所有比赛报价
          </Button>
        ) : null}
      </CardContent>
    </Card>
  )
}
