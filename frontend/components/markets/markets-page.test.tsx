import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { MarketsPage } from './markets-page'

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn() }),
}))

afterEach(cleanup)

describe('P3 markets preview', () => {
  it('exposes the three frozen views and switches their panels', async () => {
    const user = userEvent.setup()
    render(
      <MarketsPage
        initialView="opportunities"
        initialState="populated"
        initialTiers={[]}
        initialGender="all"
        initialPhase="all"
      />,
    )

    const tabs = screen.getAllByRole('tab')
    expect(tabs).toHaveLength(3)
    expect(tabs.map((tab) => tab.textContent)).toEqual(['机会BUY 与 WAIT', '全部市场覆盖与 market-only', 'Paper生命周期账本'])
    expect(screen.getByRole('tabpanel')).toHaveAttribute('id', 'markets-panel-opportunities')

    await user.click(screen.getByRole('tab', { name: /全部市场/ }))
    expect(screen.getByRole('tabpanel')).toHaveAttribute('id', 'markets-panel-all')
    expect(screen.getByText('市场筛选')).toBeVisible()

    await user.click(screen.getByRole('tab', { name: /^Paper/ }))
    expect(screen.getByRole('tabpanel')).toHaveAttribute('id', 'markets-panel-paper')
    expect(screen.getByText('Paper 生命周期账本')).toBeVisible()
  })

  it('keeps market rows internal and exposes no wallet or real-trade control', () => {
    render(
      <MarketsPage
        initialView="all"
        initialState="populated"
        initialTiers={[]}
        initialGender="all"
        initialPhase="all"
      />,
    )

    for (const link of screen.getAllByRole('link')) {
      expect(link.getAttribute('href')).toMatch(/^\/(?!\/)/)
    }
    expect(screen.queryAllByRole('button', { name: /钱包|下单|真实交易/ })).toHaveLength(0)
  })

})
