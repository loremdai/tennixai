import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { ProductHeader } from './match-header'

const { pushMock } = vi.hoisted(() => ({ pushMock: vi.fn() }))

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: pushMock }),
}))

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('ProductHeader consumer navigation', () => {
  it('uses the Home question box instead of duplicating global search', () => {
    render(<ProductHeader active="home" />)

    expect(screen.queryByLabelText('搜索球员、赛事或询问任何问题')).toBeNull()
    expect(screen.getByRole('link', { name: '市场' })).toHaveAttribute('href', '/markets')
    expect(screen.queryByRole('button', { name: '打开用户菜单' })).toBeNull()
    expect(screen.queryByRole('button', { name: '打开显示设置' })).toBeNull()
    expect(screen.queryByRole('button', { name: /查看.*通知/ })).toBeNull()
    expect(screen.queryByText('Etienne · 本地时间')).toBeNull()
  })

  it('keeps global search working from non-Home pages', async () => {
    render(<ProductHeader active="players" />)
    const search = screen.getByLabelText('搜索球员、赛事或询问任何问题')

    await userEvent.type(search, '郑钦文下一场比赛')
    await userEvent.keyboard('{Enter}')

    expect(pushMock).toHaveBeenCalledWith('/?q=%E9%83%91%E9%92%A6%E6%96%87%E4%B8%8B%E4%B8%80%E5%9C%BA%E6%AF%94%E8%B5%9B#assistant')
  })
})
