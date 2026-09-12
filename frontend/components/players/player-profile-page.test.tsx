import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { getPlayerProfileBundle } from './player-preview-data'
import { PlayerProfilePage } from './player-profile-page'

vi.mock('next/navigation', () => ({
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
    prefetch: vi.fn(),
    back: vi.fn(),
    forward: vi.fn(),
    refresh: vi.fn(),
  }),
  usePathname: () => '/players/plr_atp_ben_shelton',
  useSearchParams: () => new URLSearchParams(),
}))

const bundle = getPlayerProfileBundle('plr_atp_ben_shelton')

function renderPage() {
  return render(
    <PlayerProfilePage bundle={bundle} initialStatus="live" initialHistoryState="ready" />,
  )
}

function resultsRegion() {
  return screen.getByRole('region', { name: 'Ben Shelton 历史赛果列表' })
}

// base-ui popups open on the full mousedown/mouseup/click sequence in jsdom;
// userEvent's pointer sequence is swallowed by floating-ui outside-press handling.
function openMenu(name: string) {
  const trigger = screen.getByRole('button', { name })
  fireEvent.mouseDown(trigger)
  fireEvent.mouseUp(trigger)
  fireEvent.click(trigger)
  expect(screen.getByRole('menu')).toBeInTheDocument()
}

afterEach(cleanup)

describe('PlayerProfilePage header and current status', () => {
  it('shows the English primary name, Chinese secondary name and current ranking', () => {
    renderPage()

    expect(screen.getByRole('heading', { level: 1, name: 'Ben Shelton' })).toBeVisible()
    expect(screen.getByText('本·谢尔顿')).toBeVisible()
    expect(screen.getByText('#5')).toBeVisible()
    expect(screen.getByText('5,200')).toBeVisible()
  })

  it('links the live match card to the internal match route', () => {
    renderPage()

    const link = screen.getByRole('link', { name: '查看 Ben Shelton 的实时比赛' })
    expect(link).toHaveAttribute('href', '/matches/mtch_live_plr_atp_ben_shelton')
    // preview 状态切换按钮与 LIVE 徽章都含 “LIVE” 文案
    expect(screen.getAllByText('LIVE').length).toBeGreaterThanOrEqual(2)
  })

  it('links the next match card to the internal match route', async () => {
    const user = userEvent.setup()
    renderPage()

    await user.click(screen.getByRole('button', { name: '下一场' }))

    const link = screen.getByRole('link', { name: '查看 Ben Shelton 的下一场比赛' })
    expect(link).toHaveAttribute('href', '/matches/mtch_next_plr_atp_ben_shelton')
  })

  it('renders the exact empty copy when there is no live or next match', async () => {
    const user = userEvent.setup()
    renderPage()

    await user.click(screen.getByRole('button', { name: '暂无比赛' }))

    expect(screen.getByText('暂无比赛信息')).toBeVisible()
    expect(screen.queryByRole('link', { name: /查看 Ben Shelton 的/ })).not.toBeInTheDocument()
  })
})

describe('PlayerProfilePage season summary', () => {
  it('shows hard/clay/grass win-loss records instead of win rates', () => {
    renderPage()

    expect(screen.getByText('硬地胜负')).toBeVisible()
    expect(screen.getByText('红土胜负')).toBeVisible()
    expect(screen.getByText('草地胜负')).toBeVisible()
    expect(screen.queryByText('硬地胜率')).not.toBeInTheDocument()

    // overall W-L + three surface W-L records
    expect(screen.getAllByText(/^\d+–\d+$/).length).toBeGreaterThanOrEqual(4)
  })

  it('switches seasons and keeps summary and results in sync', async () => {
    const user = userEvent.setup()
    renderPage()

    openMenu('赛季：2026 赛季')
    await user.click(screen.getByRole('menuitem', { name: '2025 赛季' }))

    expect(screen.getByText('1–12 / 共 12 场')).toBeVisible()
    expect(screen.getByRole('button', { name: '赛季：2025 赛季' })).toBeVisible()
  })

  it('keeps surface records unavailable without faking 0–0', async () => {
    const user = userEvent.setup()
    renderPage()

    await user.click(screen.getByRole('button', { name: '资料缺失' }))

    expect(screen.getByRole('heading', { level: 1, name: 'Bryan Shelton' })).toBeVisible()
    expect(screen.getByText('暂无当前排名')).toBeVisible()
    expect(screen.getByText('该赛季统计暂不可用')).toBeVisible()
    expect(screen.getAllByText('暂无').length).toBeGreaterThanOrEqual(7)
    expect(screen.queryByText('0–0')).not.toBeInTheDocument()
  })
})

describe('PlayerProfilePage history results', () => {
  it('paginates 20 results per page', async () => {
    const user = userEvent.setup()
    renderPage()

    expect(screen.getByText('1–20 / 共 27 场')).toBeVisible()
    expect(within(resultsRegion()).getAllByRole('listitem')).toHaveLength(20)

    await user.click(screen.getByRole('button', { name: /下一页/ }))
    expect(screen.getByText('21–27 / 共 27 场')).toBeVisible()
    expect(within(resultsRegion()).getAllByRole('listitem')).toHaveLength(7)
  })

  it('links finished results to the internal match route', () => {
    renderPage()

    const links = within(resultsRegion()).getAllByRole('link')
    expect(links[0]).toHaveAttribute('href', '/matches/mtch_atp_2026_001')
    for (const link of links) {
      expect(link.getAttribute('href')).toMatch(/^\/matches\/mtch_/)
    }
  })

  it('never dates finished results after the ranking snapshot', () => {
    for (const scenario of bundle.scenarios) {
      const snapshotDate = scenario.profile.rankUpdatedAt.slice(0, 10)
      for (const result of scenario.results) {
        expect(result.date <= snapshotDate).toBe(true)
      }
    }
  })

  it('filters by tier and resets pagination', async () => {
    const user = userEvent.setup()
    renderPage()

    openMenu('赛事级别：全部级别')
    await user.click(screen.getByRole('menuitem', { name: 'ITF' }))

    const rows = within(resultsRegion()).getAllByRole('listitem')
    expect(rows).toHaveLength(2)
    for (const row of rows) {
      expect(within(row).getByText(/ITF/)).toBeVisible()
    }
    expect(screen.getByText('1–2 / 共 2 场')).toBeVisible()
  })

  it('filters by win/loss outcome', async () => {
    const user = userEvent.setup()
    renderPage()

    openMenu('赛果：全部结果')
    await user.click(screen.getByRole('menuitem', { name: '负' }))

    const rows = within(resultsRegion()).getAllByRole('listitem')
    expect(rows).toHaveLength(9)
    for (const row of rows) {
      expect(within(row).getByText('负')).toBeVisible()
      expect(within(row).queryByText('胜')).not.toBeInTheDocument()
    }
  })

  it('covers loading, empty, partial, unavailable, error and stale states', async () => {
    const user = userEvent.setup()
    renderPage()

    openMenu('切换历史赛果可用性')
    await user.click(screen.getByRole('menuitem', { name: '加载中' }))
    expect(screen.getByText('正在加载历史赛果')).toBeVisible()

    openMenu('切换历史赛果可用性')
    await user.click(screen.getByRole('menuitem', { name: '空状态' }))
    expect(screen.getByText('该赛季暂无赛果')).toBeVisible()

    openMenu('切换历史赛果可用性')
    await user.click(screen.getByRole('menuitem', { name: '部分数据' }))
    expect(screen.getByText(/只返回部分赛果/)).toBeVisible()
    expect(screen.getByText('1–8 / 共 8 场')).toBeVisible()

    openMenu('切换历史赛果可用性')
    await user.click(screen.getByRole('menuitem', { name: '历史不可用' }))
    expect(screen.getByText('历史数据暂不可用')).toBeVisible()

    openMenu('切换历史赛果可用性')
    await user.click(screen.getByRole('menuitem', { name: '加载失败' }))
    expect(screen.getByRole('alert')).toBeVisible()
    await user.click(screen.getByRole('button', { name: '重试加载' }))
    expect(screen.getByText('1–20 / 共 27 场')).toBeVisible()

    openMenu('切换历史赛果可用性')
    await user.click(screen.getByRole('menuitem', { name: '旧快照' }))
    expect(screen.getByText(/最近一次成功快照/)).toBeVisible()
    expect(screen.getByText('1–20 / 共 27 场')).toBeVisible()
  })

  it('shows the filtered-empty state without silently broadening filters', async () => {
    const user = userEvent.setup()
    renderPage()

    openMenu('赛季：2026 赛季')
    await user.click(screen.getByRole('menuitem', { name: '2022 赛季' }))
    openMenu('赛事级别：全部级别')
    await user.click(screen.getByRole('menuitem', { name: 'WTA' }))

    expect(screen.getByText('当前筛选暂无赛果')).toBeVisible()
    await user.click(screen.getByRole('button', { name: '清除赛果筛选' }))
    expect(screen.getByText('1–12 / 共 12 场')).toBeVisible()
  })
})

describe('PlayerProfilePage scenarios', () => {
  it('defaults the WTA profile to the next-match state', async () => {
    const user = userEvent.setup()
    renderPage()

    await user.click(screen.getByRole('button', { name: 'WTA 档案' }))

    expect(screen.getByRole('heading', { level: 1, name: 'Qinwen Zheng' })).toBeVisible()
    const link = screen.getByRole('link', { name: '查看 Qinwen Zheng 的下一场比赛' })
    expect(link).toHaveAttribute('href', '/matches/mtch_next_plr_wta_qinwen_zheng')
  })
})
