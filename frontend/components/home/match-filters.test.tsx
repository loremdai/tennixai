import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { MatchFiltersBar, type FacetCountsState } from './match-filters'
import { DEFAULT_MATCH_FILTERS } from '@/lib/match-filters'

const fullCounts: FacetCountsState = {
  circuits: { atp: 3, wta: 2, challenger: 1, itf: 1, other: 0 },
  genders: { men: 4, women: 3, mixed: 0, unknown: 0 },
  disciplines: { singles: 6, doubles: 1, team: 0, unknown: 0 },
}

function setup(overrides: Partial<Parameters<typeof MatchFiltersBar>[0]> = {}) {
  const onChange = vi.fn()
  const onReset = vi.fn()
  render(
    <MatchFiltersBar
      filters={DEFAULT_MATCH_FILTERS}
      facetCounts={fullCounts}
      onChange={onChange}
      onReset={onReset}
      {...overrides}
    />,
  )
  return { onChange, onReset }
}

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

describe('MatchFiltersBar', () => {
  it('exposes the three facet groups with accessible names', () => {
    setup()
    expect(screen.getByRole('group', { name: '赛事级别' })).toBeVisible()
    expect(screen.getByRole('group', { name: '性别' })).toBeVisible()
    expect(screen.getByRole('group', { name: '单双打' })).toBeVisible()
  })

  it('marks the approved defaults as active', () => {
    setup()
    expect(screen.getByRole('button', { name: /ATP/ })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('button', { name: /WTA/ })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('button', { name: /Challenger/ })).toHaveAttribute('aria-pressed', 'false')
    expect(screen.getByRole('button', { name: /单打/ })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('button', { name: /双打/ })).toHaveAttribute('aria-pressed', 'false')
  })

  it('shows result counts in each chip accessible name', () => {
    setup()
    expect(screen.getByRole('button', { name: 'ATP（3 场）' })).toBeVisible()
    expect(screen.getByRole('button', { name: '双打（1 场）' })).toBeVisible()
    expect(screen.getByRole('button', { name: '混合（0 场）' })).toBeVisible()
  })

  it('disables zero-count values that are not active', () => {
    setup()
    expect(screen.getByRole('button', { name: '混合（0 场）' })).toBeDisabled()
    expect(screen.getByRole('button', { name: '其他（0 场）' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'ATP（3 场）' })).toBeEnabled()
  })

  it('keeps an active zero-count value clickable so it can be unselected', () => {
    setup({
      filters: { ...DEFAULT_MATCH_FILTERS, circuits: ['other'] },
      facetCounts: { ...fullCounts, circuits: { ...fullCounts.circuits, other: 0 } },
    })
    expect(screen.getByRole('button', { name: '其他（0 场）' })).toBeEnabled()
  })

  it('adds a stacked value on click', async () => {
    const { onChange } = setup()
    await userEvent.click(screen.getByRole('button', { name: /女子/ }))
    expect(onChange).toHaveBeenCalledWith({
      circuits: ['atp', 'wta'],
      genders: ['women'],
      disciplines: ['singles'],
    })
  })

  it('removes a value on click without auto-selecting another', async () => {
    const { onChange } = setup()
    await userEvent.click(screen.getByRole('button', { name: /单打/ }))
    expect(onChange).toHaveBeenCalledWith({
      circuits: ['atp', 'wta'],
      genders: [],
      disciplines: [],
    })
  })

  it('shows 恢复默认 only for non-default filters and fires onReset', async () => {
    setup()
    expect(screen.queryByRole('button', { name: '恢复默认' })).toBeNull()

    cleanup()
    const { onReset } = setup({
      filters: { circuits: ['itf'], genders: [], disciplines: ['doubles'] },
    })
    const reset = screen.getByRole('button', { name: '恢复默认' })
    await userEvent.click(reset)
    expect(onReset).toHaveBeenCalledTimes(1)
  })

  it('renders without counts while loading and disables nothing', () => {
    setup({ facetCounts: null })
    expect(screen.getByRole('button', { name: 'ATP' })).toBeEnabled()
    expect(screen.getByRole('button', { name: '混合' })).toBeEnabled()
  })
})
