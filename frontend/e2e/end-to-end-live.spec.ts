import { expect, test } from '@playwright/test'

test.skip(
  process.env.TENNIX_E2E_REAL_PROVIDER !== '1' || process.env.TENNIX_E2E_REAL_LLM !== '1',
  'end-to-end live browser smoke requires TENNIX_E2E_REAL_PROVIDER=1 and TENNIX_E2E_REAL_LLM=1',
)

test('fully live smoke: trusted cards or honest empty, with model prose', async ({ page }) => {
  await page.goto('/')

  await page.getByLabel('继续向 Tennix 提问').fill('现在有什么比赛？')
  await page.getByLabel('继续向 Tennix 提问').press('Enter')

  const article = page.locator('#assistant article')
  await expect(article).toBeVisible()
  const text = (await article.textContent()) ?? ''
  expect(text.trim().length).toBeGreaterThan(0)

  const cards = page.getByRole('link', { name: /打开比赛：/ })
  const emptyCopy = page.getByText('没有符合条件的比赛')
  await expect(cards.first().or(emptyCopy)).toBeVisible()
})
