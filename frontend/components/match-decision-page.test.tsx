import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { MatchDecisionPage } from './match-decision-page'

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn() }),
}))

afterEach(cleanup)

describe('P3 match decision preview', () => {
  it('keeps the frozen mobile reading order in the DOM', () => {
    render(
      <MatchDecisionPage
        initialStatus="live"
        initialState="hold"
        initialSelection="sinner"
        initialOverlay="none"
        initialAnalysis="expanded"
        initialMethodology="closed"
        initialConfidence="high"
      />,
    )

    const sections = [
      screen.getByRole('heading', { level: 1 }),
      document.getElementById('decision-summary-title'),
      screen.getByRole('heading', { name: '比分与比赛进程' }),
      screen.getByRole('heading', { name: '关键事实' }),
      screen.getByRole('heading', { name: '比赛概览' }),
      document.getElementById('probability-market-title'),
      document.getElementById('decision-evidence-title'),
      screen.getByRole('heading', { name: '技术统计' }),
      screen.getByRole('heading', { name: '逐分与动量' }),
      document.getElementById('paper-lifecycle-title'),
      screen.getByRole('heading', { name: '本场决策助手' }),
    ]

    expect(sections.every((section) => section !== null)).toBe(true)
    for (const [index, section] of sections.slice(0, -1).entries()) {
      const currentSection = section!
      const nextSection = sections[index + 1]!
      expect(
        currentSection.compareDocumentPosition(nextSection as Node) &
          Node.DOCUMENT_POSITION_FOLLOWING,
      ).toBeTruthy()
    }
  })

  it.each([
    ['upcoming', '即将开始'],
    ['finished', '已完赛'],
  ] as const)('honors the %s preview status from the URL', (initialStatus, label) => {
    render(
      <MatchDecisionPage
        initialStatus={initialStatus}
        initialState="wait"
        initialSelection="sinner"
        initialOverlay="none"
        initialAnalysis="expanded"
        initialMethodology="closed"
        initialConfidence="high"
      />,
    )

    expect(screen.getAllByText(label).length).toBeGreaterThan(0)
  })
})
