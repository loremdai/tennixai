import { expect, test, type Page } from '@playwright/test'

const replayEnabled = process.env.TENNIX_E2E_REPLAY === '1'

type Snapshot = {
  match: { status: string }
  points: Array<{ revision: number }>
  statistics: unknown[]
  state_version: number
}

async function readSnapshot(page: Page): Promise<Snapshot> {
  const matchId = new URL(page.url()).pathname.split('/').at(-1)
  const response = await page.evaluate(async (id) => {
    const result = await fetch(`/api/matches/${id}`, { cache: 'no-store' })
    return (await result.json()).data
  }, matchId)
  return response as Snapshot
}

test.describe('P2 Replay realtime business flow', () => {
  test.skip(!replayEnabled, 'requires the deterministic Replay backend')

  test('home defaults and live Match Page update through one browser flow', async ({ page, browser }) => {
    await page.goto('/')
    await expect(page.getByRole('group', { name: '赛事级别' })).toBeVisible()
    await expect(page.getByRole('button', { name: /ATP/ })).toHaveAttribute('aria-pressed', 'true')
    await expect(page.getByRole('button', { name: /WTA/ })).toHaveAttribute('aria-pressed', 'true')
    await expect(page.getByRole('button', { name: /单打/ })).toHaveAttribute('aria-pressed', 'true')
    await expect(page.getByText('Replay Open').first()).toBeVisible()

    let pageNavigations = 0
    page.on('request', (request) => {
      if (request.resourceType() === 'document') pageNavigations += 1
    })
    await page.getByRole('link', { name: '打开比赛', exact: true }).first().click()
    await expect(page.locator('#live-scoreboard')).toBeVisible()
    const navigationsBeforeUpdates = pageNavigations
    const matchPath = new URL(page.url()).pathname
    const initial = await readSnapshot(page)
    expect(initial.state_version).toBeGreaterThanOrEqual(1)

    // A second viewer receives the same SSE/replay path while the first page
    // remains open. The backend recovery test asserts the single upstream.
    const secondContext = await browser.newContext({ viewport: { width: 390, height: 844 } })
    const secondPage = await secondContext.newPage()
    await secondPage.goto(matchPath)
    await expect(secondPage.locator('#live-scoreboard')).toBeVisible()
    await secondContext.close()

    await expect.poll(async () => (await readSnapshot(page)).points.length, { timeout: 5_000 }).toBeGreaterThanOrEqual(1)
    await expect(page.getByText('ACE 球')).toBeVisible({ timeout: 5_000 })
    await expect.poll(async () => (await readSnapshot(page)).statistics.length, { timeout: 5_000 }).toBe(22)

    // Hidden-tab release is driven by the same 60-second production timer;
    // Playwright's clock advances it without waiting a wall-clock minute.
    // Exercise it before the short replay reaches its terminal event.
    await page.clock.install()
    await page.evaluate(() => {
      Object.defineProperty(document, 'visibilityState', { configurable: true, value: 'hidden' })
      document.dispatchEvent(new Event('visibilitychange'))
    })
    await page.clock.fastForward(60_000)
    await expect(page.getByText(/暂时离开直播/)).toBeVisible({ timeout: 3_000 })
    await page.evaluate(() => {
      Object.defineProperty(document, 'visibilityState', { configurable: true, value: 'visible' })
      document.dispatchEvent(new Event('visibilitychange'))
    })
    await expect(page.locator('#live-scoreboard')).toBeVisible({ timeout: 5_000 })

    // Force a short viewport for the real PBP scroller, then inspect the old
    // point before the reconcile append. The notice must appear instead of
    // pulling the reader back to the newest point.
    const pointsScroller = page.locator('[data-points-scroller]')
    await pointsScroller.evaluate((element) => {
      element.setAttribute('style', 'height: 1px; max-height: 1px; overflow-y: auto;')
      element.scrollTop = 0
      element.dispatchEvent(new Event('scroll', { bubbles: true }))
    })
    await expect.poll(async () => (await readSnapshot(page)).points.length, { timeout: 7_000 }).toBe(2)
    await expect(page.getByRole('button', { name: /有新分/ })).toBeVisible({ timeout: 3_000 })

    await page.getByLabel('向 Tennix 询问本场比赛').fill('当前比分是多少？')
    await page.getByLabel('向 Tennix 询问本场比赛').press('Enter')
    const answerBody = page.getByTestId('markdown-answer')
    await expect(page.getByText(/已连接本场比赛上下文/)).toBeVisible({ timeout: 5_000 })
    const answerText = await answerBody.textContent()

    await expect(page.getByText('数据已校准')).toBeVisible({ timeout: 5_000 })
    await expect.poll(async () => (await readSnapshot(page)).points[0]?.revision ?? 0, { timeout: 5_000 }).toBe(2)
    await expect(page.getByText(/实时连接(?:恢复中|已恢复)/)).toBeVisible({ timeout: 7_000 })
    await expect(page.getByText(/比赛已更新；以上回答基于版本/)).toBeVisible({ timeout: 7_000 })
    await expect(answerBody).toHaveText(answerText ?? '')

    await expect(page.locator('#final-scoreboard')).toBeVisible({ timeout: 10_000 })
    await expect(page.getByText('已完赛').first()).toBeVisible()
    expect(pageNavigations).toBe(navigationsBeforeUpdates)
  })
})
