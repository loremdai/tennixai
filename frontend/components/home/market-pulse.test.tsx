import { cleanup, render, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { MarketPulse } from './market-pulse'
import { LiveMarketPulse } from './live-market-pulse'
import type { PulseViewDto } from '@/lib/api/types'

const { getMarketPulseMock } = vi.hoisted(() => ({ getMarketPulseMock: vi.fn() }))

vi.mock('@/lib/api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/lib/api/client')>()
  return { ...actual, getMarketPulse: getMarketPulseMock }
})

vi.mock('@/hooks/use-market-stream', () => ({
  useMarketStream: () => ({
    snapshot: null,
    books: {},
    decisions: {},
    paper: {},
    resolutions: {},
    gaps: [],
    phase: 'live',
    errorCode: null,
    lastEventId: null,
    refresh: async () => {},
  }),
}))

afterEach(cleanup)

describe('MarketPulse preview', () => {
  it('shows an avatar slot for each named player in a market row', () => {
    render(<MarketPulse initialState="populated" />)

    const row = screen.getByRole('link', { name: /Jannik Sinner vs Carlos Alcaraz/ })
    expect(row.querySelectorAll('[data-slot="avatar"]')).toHaveLength(2)
  })

  it('shows English first and Chinese below in a structured market-pulse player row', () => {
    render(<MarketPulse initialState="populated" />)

    const row = screen.getByRole('link', { name: /Jannik Sinner vs Carlos Alcaraz/ })
    expect(within(row).getByText('Jannik Sinner')).toBeVisible()
    expect(within(row).getByText('扬尼克·辛纳')).toBeVisible()
    expect(within(row).getByText('Carlos Alcaraz')).toBeVisible()
    expect(within(row).getByText('卡洛斯·阿尔卡拉斯')).toBeVisible()
  })

  it('shows canonical English and localized names in the live Home market pulse', async () => {
    const view: PulseViewDto = {
      has_open_position: false,
      data: [{
        match_id: 'mat_1',
        market_id: 'mkt_1',
        kind: 'opportunity',
        action: 'buy',
        phase: 'live',
        player_names: ['Jannik Sinner', 'Carlos Alcaraz'],
        player_localized_names: ['扬尼克·辛纳', '卡洛斯·阿尔卡拉斯'],
        model_probability: 0.64,
        executable_probability: 0.504,
        conservative_net_edge: '0.136',
        tournament_name: 'ATP Finals',
        is_stale: false,
        has_gap: false,
        as_of: '2026-09-26T00:00:00Z',
      }],
    }
    getMarketPulseMock.mockResolvedValue(view)

    render(<LiveMarketPulse />)

    const row = await screen.findByRole('link', { name: /Jannik Sinner vs\.? Carlos Alcaraz/ })
    expect(within(row).getByText('Jannik Sinner')).toBeVisible()
    expect(within(row).getByText('扬尼克·辛纳')).toBeVisible()
    expect(within(row).getByText('Carlos Alcaraz')).toBeVisible()
    expect(within(row).getByText('卡洛斯·阿尔卡拉斯')).toBeVisible()
  })
})
