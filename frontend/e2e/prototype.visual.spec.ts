import { expect, test } from '@playwright/test'

const states = [
  ['home-initial', '/'],
  ['home-answer', '/?q=Sinner%20%E4%BB%8A%E6%99%9A%E5%87%A0%E7%82%B9%E6%AF%94%E8%B5%9B%EF%BC%9F'],
  ['match-upcoming', '/match?status=upcoming'],
  ['match-live', '/match?status=live'],
  ['match-finished', '/match?status=finished'],
] as const

for (const [name, path] of states) {
  test(`${name} matches approved prototype`, async ({ page }) => {
    await page.goto(path)
    await page.evaluate(() => document.fonts.ready)
    await expect(page).toHaveScreenshot(`${name}.png`, {
      animations: 'disabled',
      fullPage: true,
    })
  })
}
