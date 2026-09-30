import type { KeyboardEvent } from 'react'

import { cn } from '@/lib/utils'

export type MarketsTabValue = 'opportunities' | 'all' | 'paper'

export const MARKETS_TABS: Array<{
  value: MarketsTabValue
  label: string
}> = [
  { value: 'opportunities', label: '机会' },
  { value: 'all', label: '全部市场' },
  { value: 'paper', label: '模拟记录' },
]

/** Production tablist with the approved v0 geometry (arrow-key roving). */
export function MarketsTabs({
  view,
  onSelect,
  counts,
}: {
  view: MarketsTabValue
  onSelect: (view: MarketsTabValue) => void
  counts: Record<MarketsTabValue, number>
}) {
  function handleTabKeyDown(
    event: KeyboardEvent<HTMLButtonElement>,
    index: number,
  ) {
    if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') return
    event.preventDefault()
    const offset = event.key === 'ArrowRight' ? 1 : -1
    const nextIndex = (index + offset + MARKETS_TABS.length) % MARKETS_TABS.length
    const nextView = MARKETS_TABS[nextIndex].value
    onSelect(nextView)
    document.getElementById(`markets-tab-${nextView}`)?.focus()
  }

  return (
    <div className="flex items-end justify-start gap-2 overflow-x-auto border-b sm:gap-4" role="tablist" aria-label="市场视图">
      {MARKETS_TABS.map((item, index) => (
        <button
          key={item.value}
          id={`markets-tab-${item.value}`}
          type="button"
          role="tab"
          aria-selected={view === item.value}
          aria-controls={`markets-panel-${item.value}`}
          tabIndex={view === item.value ? 0 : -1}
          onClick={() => onSelect(item.value)}
          onKeyDown={(event) => handleTabKeyDown(event, index)}
          className={cn(
            'relative flex min-h-11 shrink-0 items-center justify-center gap-2 px-3 text-sm outline-none transition-colors after:absolute after:inset-x-3 after:bottom-0 after:h-0.5 after:content-[""] focus-visible:ring-2 focus-visible:ring-ring sm:px-4',
            view === item.value
              ? 'font-semibold text-primary after:bg-primary'
              : 'text-muted-foreground after:bg-transparent hover:text-foreground',
          )}
        >
          <span>{item.label}</span>
          <span className="font-mono text-xs tabular-nums text-muted-foreground" aria-label={`${counts[item.value]} 条`}>
            {counts[item.value].toLocaleString('zh-CN')}
          </span>
        </button>
      ))}
    </div>
  )
}
