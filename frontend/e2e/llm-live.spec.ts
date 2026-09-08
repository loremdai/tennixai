import { expect, test } from '@playwright/test'

test.skip(
  process.env.TENNIX_E2E_REAL_LLM !== '1',
  'llm-live browser smoke requires TENNIX_E2E_REAL_LLM=1',
)

test('real LLM smoke: structured card plus streamed prose', async ({ page }) => {
  await page.goto('/')

  await page.getByLabel('继续向 Tennix 提问').fill('今晚 Sinner 几点比赛？')
  await page.getByLabel('继续向 Tennix 提问').press('Enter')

  const card = page.getByRole('link', { name: /打开比赛：Sinner 对阵/ }).first()
  await expect(card).toBeVisible()

  const article = page.locator('#assistant article')
  await expect(article).toBeVisible()
  const text = (await article.textContent()) ?? ''
  expect(text.trim().length).toBeGreaterThan(0)
})
