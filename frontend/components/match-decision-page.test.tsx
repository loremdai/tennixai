import { cleanup, fireEvent, render, screen } from '@testing-library/react'
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
      screen.getByRole('heading', { name: '得分走势与关键分' }),
      document.getElementById('paper-lifecycle-title'),
      screen.getByRole('heading', { name: '本场判断助手' }),
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

  it('offers supported, plain-language estimate range choices', () => {
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

    const range = screen.getByLabelText('估算范围') as HTMLSelectElement
    expect(Array.from(range.options).map((option) => [option.value, option.textContent])).toEqual([
      ['high', '较窄'],
      ['medium', '一般'],
      ['low', '较宽'],
      ['empty', '数据不足'],
      ['error', '暂不可用'],
    ])
    fireEvent.change(range, { target: { value: 'low' } })
    expect(range.value).toBe('low')
  })

  it('labels pending preview entry figures as a plan, not a completed buy', () => {
    render(
      <MatchDecisionPage
        initialStatus="live"
        initialState="entry_pending"
        initialSelection="sinner"
        initialOverlay="none"
        initialAnalysis="expanded"
        initialMethodology="closed"
        initialConfidence="high"
      />,
    )

    expect(screen.getByText('计划投入')).toBeTruthy()
    expect(screen.getByText('报价均价')).toBeTruthy()
    expect(document.body.textContent).not.toContain('模拟投入')
  })

  it('does not display a missed preview entry as invested money', () => {
    render(
      <MatchDecisionPage
        initialStatus="upcoming"
        initialState="missed"
        initialSelection="sinner"
        initialOverlay="none"
        initialAnalysis="expanded"
        initialMethodology="closed"
        initialConfidence="high"
      />,
    )

    const lifecycle = document
      .getElementById('paper-lifecycle-title')
      ?.closest('[data-slot="card"]')
    const metrics = lifecycle?.querySelectorAll('dl')
    expect(metrics?.[0]?.textContent).toBe('模拟投入—')
    expect(metrics?.[1]?.textContent).toBe('模拟买入均价—')
  })

  it('does not expose internal stage or trading-system terminology', () => {
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

    expect(document.body.textContent).not.toMatch(/P3|PREVIEW|BUY|WAIT|Paper|hard gate|STALE|DATA GAP|FOK|P&L|freshness/)
  })
})
