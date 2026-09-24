import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import { PaperRow, type PaperRowData } from './paper-row'

afterEach(cleanup)

function paperRow(overrides: Partial<PaperRowData> = {}): PaperRowData {
  return {
    id: 'paper-1',
    match: 'Alpha One vs. Beta Two',
    tournament: 'Test Open',
    direction: 'Alpha One',
    state: 'entry_pending',
    cost: 10,
    shares: 19.05,
    averageEntry: 0.525,
    currentExitValue: null,
    netPnl: null,
    freshness: '刚刚',
    detail: '正在确认模拟买入',
    href: '/matches/mat_1',
    ...overrides,
  }
}

describe('PaperRow', () => {
  it('labels unfilled entry values as estimates, not an open position', () => {
    render(<PaperRow record={paperRow()} />)

    expect(screen.getByText('计划投入 / 报价均价')).toBeTruthy()
    expect(screen.getByText('预计份额')).toBeTruthy()
    expect(screen.getByText('$10.00 · 52.5%')).toBeTruthy()
    expect(screen.getByText('19.05')).toBeTruthy()
    expect(screen.queryByText('持有份额')).toBeNull()
  })

  it('does not show zero as invested or held when an entry was missed', () => {
    render(
      <PaperRow
        record={paperRow({
          state: 'missed',
          cost: 0,
          shares: 0,
          averageEntry: null,
          detail: '模拟买入未成交',
        })}
      />,
    )

    expect(screen.getByText('模拟投入 / 买入均价')).toBeTruthy()
    expect(screen.getByText('持有份额').parentElement?.textContent).toBe('持有份额—')
    expect(screen.getByText('模拟盈亏').parentElement?.textContent).toBe('模拟盈亏—')
    expect(screen.getByText('模拟投入 / 买入均价').parentElement?.textContent).toContain('— · —')
    expect(screen.queryByText('$0.00 · —')).toBeNull()
    expect(screen.queryByText('0.00')).toBeNull()
  })
})
