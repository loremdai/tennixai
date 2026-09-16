// T71 real read-only shadow gate in a real browser.
//
// Run with the shadow backend assembled against the real API-Tennis provider
// and public Polymarket REST:
//   TENNIX_RUN_P3_SHADOW_LIVE=1 TENNIX_E2E_API_TENNIS=1 TENNIX_P3_MODE=shadow \
//     pnpm test:e2e -- e2e/p3-live.spec.ts
//
// Every flow stays read-only: no trade CTAs exist anywhere, all navigation is
// internal, and the DOM/URLs must never carry provider condition IDs, token
// IDs or wallet material. A quiet market surfaces honest empty/degraded copy
// rather than fabricated rows.

import { expect, test, type Page } from '@playwright/test'

const ENABLED = process.env.TENNIX_RUN_P3_SHADOW_LIVE === '1'

const PROVIDER_PATTERNS = [
  /0x[0-9a-fA-F]{16,}/, // polymarket condition ids
  /\b\d{20,}\b/, // asset/token ids
  /wallet/i,
  /private[-_ ]key/i,
]

function assertNoProviderMaterial(text: string, url: string) {
  for (const pattern of PROVIDER_PATTERNS) {
    expect(text, `provider material ${pattern} in DOM`).not.toMatch(pattern)
    expect(url, `provider material ${pattern} in URL`).not.toMatch(pattern)
  }
}

async function scanPage(page: Page) {
  const body = await page.evaluate(() => document.body.innerText)
  assertNoProviderMaterial(body, page.url())
}

/** Console errors minus the honest decision `not_found` 404s: a mapped match
 * without a decision context answers 404 by contract (T67), and the browser
 * logs that as a resource error. Any other 404 path fails the gate. */
function watchConsole(page: Page) {
  const consoleErrors: string[] = []
  const notFoundPaths: string[] = []
  page.on('console', (message) => {
    if (message.type() === 'error') consoleErrors.push(message.text())
  })
  page.on('response', (response) => {
    if (response.status() === 404) notFoundPaths.push(new URL(response.url()).pathname)
  })
  return {
    async assertClean() {
      const unexpected = consoleErrors.filter(
        (text) => !text.includes('React DevTools') && !text.includes('404'),
      )
      expect(unexpected).toEqual([])
      for (const path of notFoundPaths) {
        expect(
          path,
          `only honest not-found endpoints may 404 (decision context or a market-only match absent from the sports catalog), got ${path}`,
        ).toMatch(/(\/decision$|\/api\/matches\/mat_[0-9a-f]+$)/)
      }
      const logged404s = consoleErrors.filter((text) => text.includes('404')).length
      expect(logged404s).toBe(notFoundPaths.length)
    },
  }
}

test.describe('P3 live shadow read-only flows', () => {
  test.skip(!ENABLED, 'TENNIX_RUN_P3_SHADOW_LIVE not set')

  test('home pulse and markets tabs render read-only from the shadow backend', async ({ page }) => {
    const console = watchConsole(page)

    await page.goto('/')
    // Home either shows pulse rows or the honest empty/probing state; P3 off
    // keeps the P1/P2 home untouched.
    await page.waitForTimeout(2500)
    await scanPage(page)

    await page.goto('/markets')
    for (const tab of ['机会', '全部', 'Paper']) {
      await page.getByRole('tab', { name: new RegExp(tab) }).or(page.getByRole('button', { name: new RegExp(tab) })).first().click()
      await page.waitForTimeout(600)
      await scanPage(page)
    }
    // Rows (when any) are internal links only; empty state is honest copy.
    // Live data may land during the wait, so resolve rows-vs-empty as a race.
    const rows = page.locator('a[href^="/matches/"]')
    const hasRows = await rows
      .first()
      .waitFor({ state: 'visible', timeout: 20_000 })
      .then(() => true)
      .catch(() => false)
    if (hasRows) {
      await expect(rows.first()).toBeVisible()
    } else {
      await expect(page.getByText(/暂无|没有|无市场/).first()).toBeVisible()
    }
    await console.assertClean()
  })

  test('match workbench dual streams stay read-only and reconnect on refresh', async ({ page }) => {
    const console = watchConsole(page)

    await page.goto('/markets')
    await page.waitForTimeout(1500)
    const firstRow = page.locator('a[href^="/matches/"]').first()
    if ((await firstRow.count()) === 0) {
      // Honest quiet market: nothing mapped right now.
      test.info().annotations.push({
        type: 'shadow-skip',
        description: `no mapped rows on ${new Date().toISOString()}; match flow not exercised`,
      })
      return
    }
    await firstRow.click()
    await page.waitForTimeout(2500)
    await scanPage(page)
    // No trade CTA anywhere on the workbench.
    await expect(page.getByRole('button', { name: /BUY|SELL|下单|买入|卖出/ })).toHaveCount(0)

    // Refresh: snapshot-first REST restores the view, streams re-baseline.
    await page.reload()
    await page.waitForTimeout(2500)
    await scanPage(page)
    await console.assertClean()
  })
})
