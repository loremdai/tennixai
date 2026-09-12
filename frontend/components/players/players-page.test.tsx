import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  PLAYER_COUNTRY_OPTIONS,
  PLAYER_DIRECTORY,
  PLAYER_RANKINGS,
} from './player-preview-data'
import { PlayersPage, type PlayersFilters } from './players-page'

vi.mock('next/navigation', () => ({
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
    prefetch: vi.fn(),
    back: vi.fn(),
    forward: vi.fn(),
    refresh: vi.fn(),
  }),
  usePathname: () => '/players',
  useSearchParams: () => new URLSearchParams(),
}))

const defaultFilters: PlayersFilters = {
  tour: 'ATP',
  countryCode: 'ALL',
  query: '',
  page: 1,
}

function renderPage(overrides: Partial<PlayersFilters> = {}) {
  return render(
    <PlayersPage
      rankings={PLAYER_RANKINGS}
      directory={PLAYER_DIRECTORY}
      countries={PLAYER_COUNTRY_OPTIONS}
      initialFilters={{ ...defaultFilters, ...overrides }}
    />,
  )
}

async function searchFor(user: ReturnType<typeof userEvent.setup>, query: string) {
  const input = screen.getByPlaceholderText(/搜索 Ben Shelton/)
  await user.click(input)
  await user.type(input, `${query}{Enter}`)
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

describe('PlayersPage rankings mode', () => {
  it('renders the ATP Top 200 by default with official order and 50-row pagination', () => {
    renderPage()

    expect(screen.getByRole('heading', { level: 2, name: 'ATP 单打世界排名' })).toBeVisible()
    const list = screen.getByRole('region', { name: 'ATP 世界排名列表' })
    const rows = within(list).getAllByRole('listitem')
    expect(rows).toHaveLength(50)
    expect(within(rows[0]).getByText('Jannik Sinner')).toBeVisible()
    expect(within(rows[0]).getByText('扬尼克·辛纳')).toBeVisible()
    expect(screen.getByText('1–50 / 共 200 位')).toBeVisible()
    expect(screen.getByRole('button', { name: '上一页' })).toBeDisabled()
    expect(screen.getByRole('button', { name: '第 4 页' })).toBeVisible()
  })

  it('links each ranking row to the internal player profile route', () => {
    renderPage()

    const link = screen.getByRole('link', { name: /查看 Jannik Sinner，扬尼克·辛纳 的球员资料/ })
    expect(link).toHaveAttribute('href', '/players/plr_atp_jannik_sinner')
  })

  it('switches to the WTA tour without leaving the page', async () => {
    const user = userEvent.setup()
    renderPage()

    await user.click(screen.getByRole('tab', { name: 'WTA' }))

    expect(screen.getByRole('heading', { level: 2, name: 'WTA 单打世界排名' })).toBeVisible()
    expect(screen.getByText('Aryna Sabalenka')).toBeVisible()
    expect(screen.queryByText('Jannik Sinner')).not.toBeInTheDocument()
  })

  it('paginates 50 rows per page and reflects the page in the URL', async () => {
    const user = userEvent.setup()
    renderPage()

    await user.click(screen.getByRole('button', { name: '第 2 页' }))

    expect(screen.getByText('51–100 / 共 200 位')).toBeVisible()
    expect(screen.getByText(PLAYER_RANKINGS.ATP[50].name)).toBeVisible()
    expect(window.location.search).toContain('page=2')
  })

  it('filters to Chinese players with the quick filter', async () => {
    const user = userEvent.setup()
    renderPage()

    const chinaButton = screen.getByRole('button', { name: '仅看中国球员' })
    await user.click(chinaButton)

    expect(chinaButton).toHaveAttribute('aria-pressed', 'true')
    const list = screen.getByRole('region', { name: 'ATP 世界排名列表' })
    const rows = within(list).getAllByRole('listitem')
    expect(rows.length).toBeGreaterThan(0)
    for (const row of rows) {
      expect(within(row).getByText('CHN')).toBeVisible()
    }
    expect(within(list).getByText('Zhizhen Zhang')).toBeVisible()
    expect(within(list).getByText('Juncheng Shang')).toBeVisible()
    expect(within(list).getByText('Yibing Wu')).toBeVisible()
    expect(screen.getByText(`1–${rows.length} / 共 ${rows.length} 位`)).toBeVisible()
  })

  it('filters by a country picked from the dropdown', async () => {
    const user = userEvent.setup()
    renderPage()

    openMenu('选择国家或地区')
    await user.click(screen.getByRole('menuitem', { name: /意大利/ }))

    const list = screen.getByRole('region', { name: 'ATP 世界排名列表' })
    const rows = within(list).getAllByRole('listitem')
    expect(rows.length).toBeGreaterThan(0)
    for (const row of rows) {
      expect(within(row).getByText('ITA')).toBeVisible()
    }
    expect(within(list).getByText('Jannik Sinner')).toBeVisible()
    expect(within(list).getByText('Lorenzo Musetti')).toBeVisible()
  })

  it('restores the full ranking list when filters are reset', async () => {
    const user = userEvent.setup()
    renderPage()

    await user.click(screen.getByRole('button', { name: '仅看中国球员' }))
    expect(screen.queryByText('1–50 / 共 200 位')).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /重置/ }))
    expect(screen.getByText('1–50 / 共 200 位')).toBeVisible()
  })
})

describe('PlayersPage search mode', () => {
  it('finds Qinwen Zheng from the default ATP tab because search covers the full directory', async () => {
    const user = userEvent.setup()
    renderPage()

    await searchFor(user, '郑钦文')

    expect(screen.getByRole('heading', { level: 2, name: '全目录搜索结果' })).toBeVisible()
    const link = screen.getByRole('link', { name: /打开 Qinwen Zheng，郑钦文 的球员资料/ })
    expect(link).toHaveAttribute('href', '/players/plr_wta_qinwen_zheng')
    expect(within(link as HTMLElement).getByText('WTA')).toBeVisible()
  })

  it('finds Ben Shelton while the WTA tab is selected', async () => {
    const user = userEvent.setup()
    renderPage({ tour: 'WTA' })

    await searchFor(user, 'Ben Shelton')

    const link = screen.getByRole('link', { name: /打开 Ben Shelton，本·谢尔顿 的球员资料/ })
    expect(link).toHaveAttribute('href', '/players/plr_atp_ben_shelton')
  })

  it('lists same-surname candidates with rank or the fixed no-rank copy', async () => {
    const user = userEvent.setup()
    renderPage()

    await searchFor(user, 'Shelton')

    const ben = screen.getByRole('link', { name: /打开 Ben Shelton，本·谢尔顿 的球员资料/ })
    expect(ben).toBeVisible()
    expect(within(ben as HTMLElement).getByText('#5')).toBeVisible()
    const bryan = screen.getByRole('link', { name: /打开 Bryan Shelton，布莱恩·谢尔顿 的球员资料/ })
    expect(bryan).toBeVisible()
    expect(within(bryan as HTMLElement).getByText('暂无当前排名')).toBeVisible()
  })

  it('matches the provider abbreviation form B. Shelton', async () => {
    const user = userEvent.setup()
    renderPage()

    await searchFor(user, 'B. Shelton')

    expect(screen.getByRole('link', { name: /打开 Ben Shelton，本·谢尔顿 的球员资料/ })).toBeVisible()
    expect(screen.getByRole('link', { name: /打开 Bryan Shelton，布莱恩·谢尔顿 的球员资料/ })).toBeVisible()
  })

  it('shows players outside the Top 200 with their rank', async () => {
    const user = userEvent.setup()
    renderPage()

    await searchFor(user, 'Coleman Wong')

    const link = screen.getByRole('link', { name: /打开 Coleman Wong，黄泽林 的球员资料/ })
    expect(within(link as HTMLElement).getByText('#201')).toBeVisible()
  })

  it('renders a plain empty state for no matches and returns to rankings on demand', async () => {
    const user = userEvent.setup()
    renderPage()

    await searchFor(user, 'zzzznotaplayer')

    expect(screen.getByText('未找到匹配球员')).toBeVisible()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: '返回排名' }))
    expect(screen.getByRole('heading', { level: 2, name: 'ATP 单打世界排名' })).toBeVisible()
  })
})
