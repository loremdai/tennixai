import { expect, test, type Page } from '@playwright/test'

const replayEnabled = process.env.TENNIX_E2E_REPLAY === '1'

async function stabilize(page: Page) {
  await page.addStyleTag({ content: 'nextjs-portal { display: none !important; }' })
  await page.evaluate(() => {
    window.scrollTo(0, 0)
    return document.fonts.ready
  })
  await page.waitForTimeout(300)
  await page.evaluate(() => window.scrollTo({ top: 0, behavior: 'instant' }))
}

test.describe('P2 Replay visual acceptance', () => {
  test.skip(!replayEnabled, 'requires the deterministic Replay backend')

  test('home replay state matches the reviewed baseline', async ({ page }) => {
    await page.goto('/')
    await expect(page.getByText('Replay Open').first()).toBeVisible()
    await stabilize(page)
    await expect(page).toHaveScreenshot('p2-home-replay.png', {
      animations: 'disabled',
      fullPage: true,
    })
  })

  test('Match Page replay state matches the reviewed baseline', async ({ page }) => {
    await page.goto('/')
    await page.getByRole('link', { name: '打开比赛', exact: true }).first().click()
    await expect(page.locator('#live-scoreboard')).toBeVisible()
    await stabilize(page)
    await expect(page).toHaveScreenshot('p2-match-replay.png', {
      animations: 'disabled',
      fullPage: true,
    })
  })
})
