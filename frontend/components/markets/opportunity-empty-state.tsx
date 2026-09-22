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
    title: '暂无符合门槛的机会',
    body: '覆盖市场仍在监测中；下一次通过 hard gate 的 BUY 或 WAIT 会出现在这里。',
    offersAllMarkets: false,
  },
  ELIGIBLE_UNPROMOTED: {
    title: '模型尚未完成验证',
    body: '模型尚未完成验证，当前不生成 BUY / WAIT；全部市场的真实报价仍可查看。',
    offersAllMarkets: true,
  },
  NO_ELIGIBLE_ACTION: {
    title: '当前没有机会',
    body: '当前没有满足策略门的机会。',
    offersAllMarkets: true,
  },
  NO_COVERED_MARKET: {
    title: '暂无可评估市场',
    body: '当前没有可评估的主巡单打市场。',
    offersAllMarkets: true,
  },
  DECISION_GAP: {
    title: '决策数据恢复中',
    body: '决策数据正在恢复，暂不生成新机会。',
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
            查看全部市场
          </Button>
        ) : null}
      </CardContent>
    </Card>
  )
}