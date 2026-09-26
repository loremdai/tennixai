import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import { MarketPulse } from './market-pulse'

afterEach(cleanup)

describe('MarketPulse preview', () => {
  it('shows an avatar slot for each named player in a market row', () => {
    render(<MarketPulse initialState="populated" />)

    const row = screen.getByRole('link', { name: /Jannik Sinner vs Carlos Alcaraz/ })
    expect(row.querySelectorAll('[data-slot="avatar"]')).toHaveLength(2)
  })
})
