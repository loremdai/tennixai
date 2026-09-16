import type { KeyboardEvent } from 'react'

import { cn } from '@/lib/utils'

export type MarketsTabValue = 'opportunities' | 'all' | 'paper'

export const MARKETS_TABS: Array<{
  value: MarketsTabValue
  label: string
  description: string
}> = [
  { value: 'opportunities', label: '机会', description: 'BUY 与 WAIT' },
  { value: 'all', label: '全部市场', description: '覆盖与 market-only' },
  { value: 'paper', label: 'Paper', description: '生命周期账本' },
]

/** Production tablist with the approved v0 geometry (arrow-key roving). */
export function MarketsTabs({
  view,
  onSelect,
}: {
  view: MarketsTabValue
  onSelect: (view: MarketsTabValue) => void
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
    <div className="flex overflow-x-auto rounded-xl border bg-card p-1" role="tablist" aria-label="市场视图">
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
            'flex min-h-11 min-w-28 flex-1 flex-col items-center justify-center rounded-lg px-4 py-2 text-sm outline-none transition-colors focus-visible:ring-2 focus-visible:ring-ring',
            view === item.value ? 'bg-secondary font-semibold text-foreground' : 'text-muted-foreground hover:text-foreground',
          )}
        >
          <span>{item.label}</span>
          <span className="hidden text-xs font-normal text-muted-foreground sm:block">{item.description}</span>
        </button>
      ))}
    </div>
  )
}
