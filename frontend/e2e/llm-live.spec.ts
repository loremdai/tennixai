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

test('real LLM global match question keeps data after planning', async ({ page }) => {
  const consoleErrors: string[] = []
  const pageErrors: string[] = []
  page.on('console', (message) => {
    if (message.type() === 'error') consoleErrors.push(message.text())
  })
  page.on('pageerror', (error) => pageErrors.push(error.message))

  await page.goto('/')

  const input = page.getByLabel('继续向 Tennix 提问')
  await input.fill('Sinner 的比赛如何了')
  await input.press('Enter')

  await expect(
    page.getByText(/正在(?:锁定比赛快照|拆解问题|读取比赛数据|组织回答)…/).first(),
  ).toBeVisible({ timeout: 10000 })

  const assistant = page.locator('#assistant')
  await expect(page.getByRole('link', { name: /打开比赛：Sinner 对阵/ }).first()).toBeVisible({
    timeout: 45000,
  })
  await expect(assistant).not.toContainText('查询未完成')
  await expect(assistant).not.toContainText('查询失败（invalid_request）')

  expect(pageErrors).toEqual([])
  expect(consoleErrors).toEqual([])
})
