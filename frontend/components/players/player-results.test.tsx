import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { PlayerResults } from '@/components/players/player-results'

afterEach(cleanup)

describe('PlayerResults server-driven empty states', () => {
  it('does not claim the player had no matches when the provider returned no rows', () => {
    render(
      <PlayerResults
        playerName="Ben Shelton"
        playerTour="ATP"
        results={[]}
        historyState="empty"
        season={2026}
        onSeasonChange={vi.fn()}
        onRetry={vi.fn()}
        tier="ALL"
        onTierChange={vi.fn()}
        outcome="ALL"
        onOutcomeChange={vi.fn()}
        page={1}
        onPageChange={vi.fn()}
        total={0}
      />,
    )

    expect(screen.getByText('暂无可显示的逐场赛果')).toBeVisible()
    expect(screen.getByText(/赛季统计可能仍可查看/)).toBeVisible()
  })

  it('explains an empty active filter and lets the user clear it', async () => {
    const user = userEvent.setup()
    const onTierChange = vi.fn()
    const onOutcomeChange = vi.fn()
    const onPageChange = vi.fn()

    render(
      <PlayerResults
        playerName="Ben Shelton"
        playerTour="ATP"
        results={[]}
        historyState="empty"
        season={2026}
        onSeasonChange={vi.fn()}
        onRetry={vi.fn()}
        tier="ITF"
        onTierChange={onTierChange}
        outcome="ALL"
        onOutcomeChange={onOutcomeChange}
        page={1}
        onPageChange={onPageChange}
        total={0}
      />,
    )

    expect(screen.getByText('当前筛选暂无赛果')).toBeVisible()
    expect(screen.getByRole('button', { name: '清除赛果筛选' })).toBeVisible()

    await user.click(screen.getByRole('button', { name: '清除赛果筛选' }))

    expect(onTierChange).toHaveBeenCalledWith('ALL')
    expect(onOutcomeChange).toHaveBeenCalledWith('ALL')
    expect(onPageChange).toHaveBeenCalledWith(1)
  })
})
