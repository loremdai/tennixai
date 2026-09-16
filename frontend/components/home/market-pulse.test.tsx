import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import { MarketPulse } from './market-pulse'

afterEach(cleanup)

describe('P3 Home market pulse preview', () => {
  it('shows at most three rows and keeps every row link internal', () => {
    render(<MarketPulse initialState="populated" />)

    const rowLinks = screen.getAllByRole('link').filter((link) =>
      link.getAttribute('aria-label')?.startsWith('查看 '),
    )

    expect(rowLinks).toHaveLength(3)
    for (const link of rowLinks) {
      expect(link.getAttribute('href')).toMatch(/^\/(?!\/)/)
    }
    expect(screen.queryAllByRole('button', { name: /钱包|下单|真实交易/ })).toHaveLength(0)
  })

  it('uses a distinct empty state instead of filling the pulse with weak rows', () => {
    render(<MarketPulse initialState="empty" />)

    expect(screen.getByText('暂无符合门槛的市场机会')).toBeVisible()
    expect(screen.queryAllByRole('link', { name: /查看 .*决策/ })).toHaveLength(0)
  })
})
