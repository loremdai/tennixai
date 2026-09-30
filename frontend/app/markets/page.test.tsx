import type { ReactElement } from 'react'
import { describe, expect, it } from 'vitest'

import Page from './page'
import type { CircuitTier } from '@/lib/api/types'
import type { MarketsTabValue } from '@/components/markets/markets-tabs'

describe('production markets route filters', () => {
  it('opens the approved all-markets view by default', async () => {
    const page = (await Page({ searchParams: Promise.resolve({}) })) as ReactElement<{
      initialView: MarketsTabValue
    }>

    expect(page.props.initialView).toBe('all')
  })

  it('defaults to ATP and WTA markets', async () => {
    const page = (await Page({ searchParams: Promise.resolve({}) })) as ReactElement<{
      initialTiers: CircuitTier[]
    }>

    expect(page.props.initialTiers).toEqual(['atp', 'wta'])
  })

  it('treats tier=all as an explicit request for every tier', async () => {
    const page = (await Page({
      searchParams: Promise.resolve({ tier: 'all' }),
    })) as ReactElement<{ initialTiers: CircuitTier[] }>

    expect(page.props.initialTiers).toEqual([])
  })
})
