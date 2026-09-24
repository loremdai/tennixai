import { expect, test, type Page } from '@playwright/test'

async function preparePage(page: Page, path: string) {
  await page.goto(path)
  // Hide the nondeterministic Next.js dev overlay host, matching the prototype suite.
  await page.addStyleTag({ content: 'nextjs-portal { display: none !important; }' })
}

const states: Array<[string, (page: Page) => Promise<void>]> = [
  ['p1-home-initial', async (page) => {
    await preparePage(page, '/')
    await page.getByRole('link', { name: '打开 Sinner 对阵 Ruud' }).first().waitFor()
  }],
  ['p1-home-result', async (page) => {
    await preparePage(page, '/?q=' + encodeURIComponent('Sinner 今晚几点比赛？'))
    await page.getByRole('link', { name: /打开比赛：Sinner 对阵/ }).first().waitFor()
    await expect(page.getByLabel('发送问题')).toBeEnabled()
    await expect(page.getByText('正在组织回答…')).toHaveCount(0)
  }],
  ['p1-home-error', async (page) => {
    await page.route('**/api/matches**', (route) => {
      const url = route.request().url()
      if (url.includes('/api/matches?') || url.includes('/api/matches/catalog?')) {
        return route.fulfill({
          status: 503,
          contentType: 'application/json',
          body: JSON.stringify({
            error: { code: 'provider_unavailable', message: 'LiveTennisAPI request failed', details: {} },
            request_id: 'req-visual',
          }),
        })
      }
      return route.continue()
    })
    await preparePage(page, '/')
    await page.getByText('比赛信息暂时无法加载，请稍后重试。').waitFor()
  }],
  ['p1-match-live', async (page) => {
    await preparePage(page, '/')
    await page.getByRole('link', { name: '打开比赛', exact: true }).click()
    await page.locator('#match').waitFor()
    await page.getByText('本场比赛暂未提供技术统计。').first().waitFor()
  }],
  ['p1-match-upcoming', async (page) => {
    await preparePage(page, '/?q=' + encodeURIComponent('Sinner 今晚几点比赛？'))
    await page.getByRole('link', { name: /打开比赛：Sinner 对阵 Alcaraz/ }).first().click()
    await page.locator('#match').waitFor()
    await page.getByText('比赛开始后查看技术统计').first().waitFor()
  }],
  ['p1-preview-finished', async (page) => {
    await preparePage(page, '/match?status=finished')
    await page.locator('#final-scoreboard').waitFor()
  }],
]

test.describe('P1 visual baselines', { tag: '@visual' }, () => {
  for (const [name, prepare] of states) {
    test(`${name} matches the current P1 interface`, async ({ page }) => {
      await prepare(page)
      await page.evaluate(() => {
        window.scrollTo(0, 0)
        return document.fonts.ready
      })
      // Let any scheduled smooth scroll run to completion, then pin the viewport
      // back to the top so sticky-header baselines stay repeatable.
      await page.waitForTimeout(600)
      await page.evaluate(
        () =>
          new Promise((resolve) => {
            window.scrollTo({ top: 0, behavior: 'instant' })
            requestAnimationFrame(() => resolve(null))
          }),
      )
      await expect(page).toHaveScreenshot(`${name}.png`, {
        animations: 'disabled',
        fullPage: true,
      })
    })
  }
})
