// T69 chart contract: both players keep independent executable asks (no
// forced 100% complement), the $10 numbers agree with the backend strings,
// missing samples render as gaps instead of interpolated lines, and the
// chart carries a textual summary plus accessible series names.
import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import { ProbabilityMarketChart } from './probability-market-chart'
import type { DecisionSnapshotDto } from '@/lib/api/types'
import { toChartSides, type TrajectoryPointModel } from '@/lib/p3-workbench-models'

afterEach(cleanup)

const names: Record<string, string> = { ply_a: 'Alpha One', ply_b: 'Beta Two' }

function snapshot(overrides: Partial<DecisionSnapshotDto> = {}): DecisionSnapshotDto {
  return {
    match_id: 'mat_1',
    market_id: 'mkt_1',
    action: 'buy',
    reason_code: null,
    target_player_id: 'ply_a',
    observation_version: 1,
    model_probabilities: { ply_a: 0.62, ply_b: 0.38 },
    model_availability: 'available',
    quote_average_price: '0.525',
    quote_side: 'entry',
    conservative_net_edge: '0.0700',
    max_acceptable_price: null,
    hold_value: null,
    model_version: 'm',
    calibration_version: 'c',
    policy_version: 'p',
    data_version: 'd',
    gates: [],
    outcome_levels: [
      { player_id: 'ply_a', best_bid: '0.55', best_ask: '0.57' },
      { player_id: 'ply_b', best_bid: '0.43', best_ask: '0.45' },
    ],
    position: null,
    lifecycle: [],
    is_stale: false,
    has_gap: false,
    lock_profit_available: false,
    as_of: '2026-09-16T11:59:30Z',
    ...overrides,
  }
}

const trajectory: TrajectoryPointModel[] = [
  { time: '20:01:00', model: 0.6, market: 0.55, uncertainty: null },
  { time: '20:02:00', model: 0.62, market: null, uncertainty: null },
]

describe('toChartSides', () => {
  it('keeps both sides independent — asks never forced to complement', () => {
    const sides = toChartSides(snapshot(), names)
    expect(sides).toHaveLength(2)
    // 0.57 + 0.45 = 1.02: a real two-sided book, not 1 - ask.
    expect(sides[0].ask).toBeCloseTo(0.57)
    expect(sides[1].ask).toBeCloseTo(0.45)
    expect(sides[1].ask).not.toBeCloseTo(1 - 0.57)
    expect(sides[0].modelProbability).toBeCloseTo(0.62)
    expect(sides[1].modelProbability).toBeCloseTo(0.38)
    expect(sides[0].selected).toBe(true)
    expect(sides[1].selected).toBe(false)
  })

  it('keeps one-sided books honest', () => {
    const sides = toChartSides(
      snapshot({
        outcome_levels: [
          { player_id: 'ply_a', best_bid: null, best_ask: '0.57' },
          { player_id: 'ply_b', best_bid: '0.43', best_ask: null },
        ],
      }),
      names,
    )
    expect(sides[0].bid).toBeNull()
    expect(sides[1].ask).toBeNull()
  })
})

describe('ProbabilityMarketChart', () => {
  it('renders per-side server values and a textual summary', () => {
    render(
      <ProbabilityMarketChart sides={toChartSides(snapshot(), names)} trajectory={trajectory} overlay="none" />,
    )
    const sideTexts = screen
      .getAllByText(/胜率 /)
      .map((element) => element.closest('p')?.textContent ?? element.textContent)
    expect(sideTexts).toContain('胜率 62.0% / 买入价 57.0%')
    expect(sideTexts).toContain('胜率 38.0% / 买入价 45.0%')
    expect(screen.getByRole('note').textContent).toContain('你关注的球员是 Alpha One')
    expect(screen.getByRole('note').textContent).toContain('10 美元模拟买入价为 57.0%')
    expect(screen.getByText('当前选择')).toBeTruthy()
  })

  it('exposes accessible series names and a screen-reader data table', () => {
    render(
      <ProbabilityMarketChart sides={toChartSides(snapshot(), names)} trajectory={trajectory} overlay="none" />,
    )
    expect(
      screen.getByRole('table', { name: '本次打开页面后的胜率与模拟买入价记录' }),
    ).toBeTruthy()
    const headers = screen.getAllByRole('columnheader').map((cell) => cell.textContent)
    expect(headers).toEqual(['时间', '模型估算胜率', '模拟买入价'])
  })

  it('renders missing samples as gaps, never interpolated values', () => {
    render(
      <ProbabilityMarketChart sides={toChartSides(snapshot(), names)} trajectory={trajectory} overlay="gap" />,
    )
    const cells = screen.getAllByRole('cell').map((cell) => cell.textContent)
    // Row 2 market sample is missing: show a clear absence, never an invented value.
    expect(cells).toContain('暂无数据')
    expect(cells.filter((text) => text === '暂无数据')).toHaveLength(1)
    expect(screen.getByText('比赛数据暂时中断')).toBeTruthy()
  })

  it('shows the honest accumulation state before any sample exists', () => {
    render(
      <ProbabilityMarketChart sides={toChartSides(snapshot(), names)} trajectory={[]} overlay="none" />,
    )
    expect(screen.getByText(/本次打开页面后才开始记录/)).toBeTruthy()
    expect(screen.queryByText('暂无数据')).toBeNull()
  })

  it('never fabricates prices when the book is absent', () => {
    render(
      <ProbabilityMarketChart sides={toChartSides(snapshot({ outcome_levels: [] }), names)} trajectory={[]} overlay="none" />,
    )
    expect(screen.getByText('暂无可用市场报价。')).toBeTruthy()
  })
})
