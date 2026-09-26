import { cleanup, render, screen } from '@testing-library/react'
import type { ComponentProps, ImgHTMLAttributes, ReactNode } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/components/ui/avatar', () => ({
  Avatar: ({ children, className, ...props }: ComponentProps<'div'> & { children: ReactNode }) => (
    <div className={className} data-slot="avatar" {...props}>{children}</div>
  ),
  AvatarImage: (props: ImgHTMLAttributes<HTMLImageElement>) => (
    <img data-slot="avatar-image" {...props} />
  ),
  AvatarFallback: ({ children, className }: { children: ReactNode; className?: string }) => (
    <span className={className} data-slot="avatar-fallback">{children}</span>
  ),
}))

import { PlayerAvatar } from './player-avatar'

afterEach(cleanup)

describe('PlayerAvatar', () => {
  it('renders the supplied player photo with an accessible name', () => {
    render(
      <PlayerAvatar
        name="Jannik Sinner"
        imageUrl="https://images.example/sinner.jpg"
        className="size-12"
      />,
    )

    const avatar = screen.getByRole('img', { name: 'Jannik Sinner 头像' })
    expect(avatar.querySelector('[data-slot="avatar-image"]')).toHaveAttribute(
      'src',
      'https://images.example/sinner.jpg',
    )
  })

  it('uses a neutral silhouette, never name initials, when the photo is absent', () => {
    const { container } = render(<PlayerAvatar name="Jannik Sinner" imageUrl={null} />)

    expect(screen.getByRole('img', { name: 'Jannik Sinner 头像' })).toBeInTheDocument()
    expect(container.querySelector('[data-slot="avatar-fallback"] svg')).not.toBeNull()
    expect(screen.queryByText('JS')).not.toBeInTheDocument()
  })
})
