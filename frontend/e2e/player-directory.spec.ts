import { expect, test, type Page } from '@playwright/test'

/**
 * Deterministic functional gate for the production `/players` pages against
 * the fake-provider backend (playwright.config webServer). The dataset is the
 * seeded directory: ATP has 5 ranked members (incl. the rank-200 boundary and
 * one rank outside 200), WTA has 2; only English aliases exist, so a Chinese
 * query must render the honest not-found state instead of failing.
 */

const searchInput = (page: Page) => page.locator('#player-directory-search')

async function openMenu(page: Page, triggerLabel: string, itemLabel: string) {
  await page.getByRole('button', { name: triggerLabel }).click()
  await page.getByRole('menuitem', { name: itemLabel }).click()
}

test.describe('player directory', () => {
  test('player directory - rankings, tour switch and China filter', async ({ page }) => {
    await page.goto('/players')

    await expect(page.getByRole('heading', { name: 'ATP 单打世界排名' })).toBeVisible()
    await expect(page.getByRole('link', { name: /Jannik Sinner/ })).toBeVisible()
    // The page is bounded to the official Top 200; the rank-200 boundary row
    // shows while the seeded rank-201 player stays search-only (next test).
    await expect(page.getByRole('link', { name: /Zhizhen Zhang/ })).toBeVisible()
    await expect(page.getByRole('link', { name: /Coleman Wong/ })).toHaveCount(0)
    await expect(page.getByText('共 4 位')).toBeVisible()

    await page.getByRole('tab', { name: 'WTA' }).click()
    await expect(page.getByRole('heading', { name: 'WTA 单打世界排名' })).toBeVisible()
    await expect(page.getByRole('link', { name: /Qinwen Zheng/ })).toBeVisible()
    await expect(page.getByText('共 2 位')).toBeVisible()
    await expect(page).toHaveURL(/tour=WTA/)

    await page.getByRole('button', { name: '仅看中国球员' }).click()
    await expect(page.getByRole('link', { name: /Qinwen Zheng/ })).toBeVisible()
    await expect(page.getByRole('link', { name: /Iga Swiatek/ })).toHaveCount(0)
    await expect(page).toHaveURL(/country=CHN/)
  })

  test('player directory - search spans tours and outside-200 ranks', async ({ page }) => {
    await page.goto('/players')
    await expect(page.getByRole('heading', { name: 'ATP 单打世界排名' })).toBeVisible()

    // Typing a WTA name on the default ATP tab searches the full directory.
    await searchInput(page).fill('Zheng')
    await searchInput(page).press('Enter')
    await expect(page.getByRole('heading', { name: '全目录搜索结果' })).toBeVisible()
    const zhengResult = page.getByRole('link', { name: /Qinwen Zheng/ })
    await expect(zhengResult).toBeVisible()
    await expect(page.getByText('#5')).toBeVisible()
    await expect(page).toHaveURL(/q=Zheng/)

    await page.getByRole('button', { name: '清空球员搜索' }).click()
    await expect(page.getByRole('heading', { name: 'ATP 单打世界排名' })).toBeVisible()

    // The 排名 201 quick chip resolves a player seeded outside the Top 200.
    await page.getByRole('button', { name: '排名 201' }).click()
    await expect(page.getByRole('link', { name: /Coleman Wong/ })).toBeVisible()
    await expect(page.getByText('#201')).toBeVisible()
  })

  test('player directory - Chinese query renders the honest empty state in fake mode', async ({ page }) => {
    await page.goto('/players')
    await expect(page.getByRole('heading', { name: 'ATP 单打世界排名' })).toBeVisible()

    await searchInput(page).fill('郑钦文')
    await searchInput(page).press('Enter')

    // The deterministic fake directory only carries English aliases; the page
    // must show the recoverable not-found state, never an error crash.
    await expect(page.getByText('未找到匹配球员')).toBeVisible()
    await expect(page.getByRole('button', { name: '返回排名' })).toBeVisible()
  })

  test('player directory - profile shows live status and navigates to finished matches', async ({ page }) => {
    await page.goto('/players')
    await page.getByRole('link', { name: /Jannik Sinner/ }).click()

    await expect(page.getByRole('heading', { level: 1, name: 'Jannik Sinner' })).toBeVisible()
    // Live match card beats next/none for the seeded live fixture.
    const statusCard = page.locator('[aria-labelledby="current-status-title"]')
    await expect(page.getByRole('heading', { name: '当前比赛状态' })).toBeVisible()
    await expect(statusCard.getByText('LIVE')).toBeVisible()
    await expect(statusCard.getByText('Casper Ruud')).toBeVisible()
    await expect(page.getByRole('link', { name: /查看 Jannik Sinner 的实时比赛/ })).toBeVisible()

    // Season summary reflects the deterministic fake season record.
    await expect(page.getByRole('heading', { name: '赛季摘要' })).toBeVisible()
    await expect(page.getByText('30–10')).toBeVisible()

    // The seeded fake dataset pairs every other member's finished matches
    // with this player, so 2026 totals 8 × 23 = 184 deterministic rows.
    const results = page.getByRole('region', { name: 'Jannik Sinner 历史赛果列表' })
    await expect(results).toBeVisible()
    await expect(page.getByText('1–20 / 共 184 场')).toBeVisible()

    await results.getByRole('link').first().click()
    await page.waitForURL(/\/matches\/[^/]+$/)
  })

  test('player directory - empty current status, season switch, filters and pagination', async ({ page }) => {
    await page.goto('/players?tour=WTA')
    await page.getByRole('link', { name: /Qinwen Zheng/ }).click()

    await expect(page.getByRole('heading', { level: 1, name: 'Qinwen Zheng' })).toBeVisible()
    // No live or upcoming fixture for this player: the exact empty copy shows.
    await expect(page.getByText('暂无比赛信息')).toBeVisible()

    await expect(page.getByText('1–20 / 共 23 场')).toBeVisible()
    await page.getByRole('button', { name: '下一页' }).last().click()
    await expect(page.getByText('21–23 / 共 23 场')).toBeVisible()

    await openMenu(page, '赛季：2026 赛季', '2025 赛季')
    await expect(page.getByText('1–5 / 共 5 场')).toBeVisible()

    await openMenu(page, '赛季：2025 赛季', '2022 赛季')
    await expect(page.getByText('历史数据暂不可用')).toBeVisible()

    await openMenu(page, '赛季：2022 赛季', '2026 赛季')
    await openMenu(page, '赛事级别：全部级别', 'Challenger')
    await expect(page.getByText('1–2 / 共 2 场')).toBeVisible()

    await openMenu(page, '赛果：全部结果', '胜')
    await expect(page.getByRole('button', { name: '重置赛果筛选' })).toBeVisible()
    await page.getByRole('button', { name: '重置赛果筛选' }).click()
    await expect(page.getByText('1–20 / 共 23 场')).toBeVisible()
  })
})
