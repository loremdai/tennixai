import { cleanup, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { PlayerAvatar } from './player-avatar'

class FailedImage {
  onload: (() => void) | null = null
  onerror: (() => void) | null = null
  complete = false
  naturalWidth = 0
  crossOrigin: string | null = null
  referrerPolicy = ''

  set src(_value: string) {
    queueMicrotask(() => this.onerror?.())
  }
}

beforeEach(() => vi.stubGlobal('Image', FailedImage))
afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe('PlayerAvatar image failures', () => {
  it('shows the neutral fallback when the provider photo cannot load', async () => {
    render(
      <PlayerAvatar
        name="Jannik Sinner"
        imageUrl="https://images.example/unavailable.jpg"
      />,
    )

    const avatar = screen.getByRole('img', { name: 'Jannik Sinner 头像' })
    await waitFor(() =>
      expect(avatar.querySelector('[data-slot="avatar-fallback"] svg')).not.toBeNull(),
    )
  })
})
