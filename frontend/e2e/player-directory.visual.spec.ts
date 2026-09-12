import { expect, test, type Page } from '@playwright/test'

async function preparePage(page: Page, path: string) {
  await page.goto(path)
  // Hide the nondeterministic Next.js dev overlay host, matching the prototype suite.
  await page.addStyleTag({ content: 'nextjs-portal { display: none !important; }' })
  await page.evaluate(() => document.fonts.ready)
  // Flag CDN and local avatar images must be fully decoded before snapshotting.
  await page.waitForFunction(
    () => Array.from(document.images).every((img) => img.complete),
    undefined,
    { timeout: 20_000 },
  )
  // Neither viewport may scroll horizontally.
  await page.waitForFunction(
    () => document.documentElement.scrollWidth <= document.documentElement.clientWidth,
    undefined,
    { timeout: 5_000 },
  )
}

const states: Array<[name: string, path: string, ready: (page: Page) => Promise<void>]> = [
  [
    'players-directory',
    '/players',
    async (page) => {
      await page.getByRole('heading', { name: 'ATP 单打世界排名' }).waitFor()
    },
  ],
  [
    'players-profile',
    '/players/plr_atp_ben_shelton',
    async (page) => {
      await page.getByRole('heading', { level: 1, name: 'Ben Shelton' }).waitFor()
    },
  ],
]

for (const [name, path, ready] of states) {
  test(`player directory visual - ${name}`, async ({ page }) => {
    await preparePage(page, path)
    await ready(page)
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
