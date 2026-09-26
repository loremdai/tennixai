import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import { PlayerName } from './player-name'

afterEach(cleanup)

describe('PlayerName', () => {
  it('shows English first and a localized name beneath it', () => {
    render(<PlayerName name="Jannik Sinner" localizedName="扬尼克·辛纳" />)

    expect(screen.getByText('Jannik Sinner')).toBeVisible()
    expect(screen.getByText('扬尼克·辛纳')).toBeVisible()
  })

  it.each([null, '  '])('hides a missing or blank localized name (%s)', (localizedName) => {
    render(<PlayerName name="Jannik Sinner" localizedName={localizedName} />)

    expect(screen.getByText('Jannik Sinner')).toBeVisible()
    expect(screen.queryByText('扬尼克·辛纳')).not.toBeInTheDocument()
  })
})
