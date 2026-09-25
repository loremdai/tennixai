import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import { PlayerSeasonSummary } from '@/components/players/player-season-summary'
import type { PlayerSeasonSummaryPreview } from '@/components/players/player-preview-data'

afterEach(cleanup)

describe('PlayerSeasonSummary', () => {
  it('shows available recorded-results metrics and omits unavailable ones', () => {
    const summary: PlayerSeasonSummaryPreview = {
      season: 2026,
      matches: 47,
      wins: 44,
      losses: 3,
      winRate: 93.6,
      titles: null,
      hard: null,
      clay: null,
      grass: null,
      resultBasis: 'recorded_results',
    }

    render(<PlayerSeasonSummary summary={summary} />)

    expect(screen.getByRole('heading', { name: '赛季摘要' })).toBeVisible()
    expect(screen.getByText('比赛场次')).toBeVisible()
    expect(screen.getByText('47')).toBeVisible()
    expect(screen.getByText('44–3')).toBeVisible()
    expect(screen.getByText('93.6%')).toBeVisible()
    for (const label of ['比赛场次', '胜–负', '胜率']) {
      expect(screen.getByText(label).parentElement).toHaveTextContent('按收录单打赛果计算')
    }
    expect(screen.queryByText('冠军数')).not.toBeInTheDocument()
    expect(screen.queryByText('硬地胜负')).not.toBeInTheDocument()
    expect(screen.queryByText('暂无')).not.toBeInTheDocument()
  })

  it('hides the card when no summary metric is available', () => {
    const summary: PlayerSeasonSummaryPreview = {
      season: 2026,
      matches: null,
      wins: null,
      losses: null,
      winRate: null,
      titles: null,
      hard: null,
      clay: null,
      grass: null,
    }

    render(<PlayerSeasonSummary summary={summary} />)

    expect(screen.queryByRole('heading', { name: '赛季摘要' })).not.toBeInTheDocument()
  })

  it('labels only locally derived metrics when provider stats are also present', () => {
    const summary: PlayerSeasonSummaryPreview = {
      season: 2026,
      matches: 47,
      wins: 44,
      losses: 3,
      winRate: 93.6,
      titles: 6,
      hard: { won: 39, lost: 3 },
      clay: null,
      grass: null,
      resultBasis: 'recorded_results',
    }

    render(<PlayerSeasonSummary summary={summary} />)

    for (const label of ['比赛场次', '胜–负', '胜率']) {
      expect(screen.getByText(label).parentElement).toHaveTextContent('按收录单打赛果计算')
    }
    expect(screen.getByText('冠军数').parentElement).not.toHaveTextContent('按收录单打赛果计算')
    expect(screen.getByText('硬地胜负').parentElement).not.toHaveTextContent('按收录单打赛果计算')
  })
})
