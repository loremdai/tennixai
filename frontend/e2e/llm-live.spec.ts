import { expect, test } from '@playwright/test'

test.skip(
  process.env.TENNIX_E2E_REAL_LLM !== '1',
  'llm-live browser smoke requires TENNIX_E2E_REAL_LLM=1',
)

async function waitForCompleteAnswer(page: import('@playwright/test').Page): Promise<string> {
  const assistant = page.locator('#assistant')
  await expect(assistant.getByRole('button', { name: '发送问题' })).toBeEnabled({ timeout: 60_000 })
  const answer = assistant.getByTestId('markdown-answer')
  await expect(answer).toBeVisible({ timeout: 5_000 })
  await expect(answer).toHaveText(/\S+/, { timeout: 5_000 })
  await expect(assistant).not.toContainText('查询未完成')
  await expect(assistant).not.toContainText('查询失败')

  const text = (await answer.textContent())?.trim() ?? ''
  expect(text.length).toBeGreaterThan(40)
  return text
}

test('real LLM smoke: structured card plus streamed prose', async ({ page }) => {
  await page.goto('/')

  await page.getByLabel('继续向 Tennix 提问').fill('今晚 Sinner 几点比赛？')
  await page.getByLabel('继续向 Tennix 提问').press('Enter')

  const card = page.getByRole('link', { name: /打开比赛：Sinner 对阵/ }).first()
  await expect(card).toBeVisible()

  const text = await waitForCompleteAnswer(page)
  expect(text).toMatch(/Sinner|20:30|18:00|12:30/)
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
  const answer = await waitForCompleteAnswer(page)
  expect(answer).toMatch(/Sinner|Alcaraz|Ruud|Djokovic/)
  await expect(assistant).not.toContainText('查询未完成')
  await expect(assistant).not.toContainText('查询失败（invalid_request）')

  expect(pageErrors).toEqual([])
  expect(consoleErrors).toEqual([])
})

test('real LLM match analysis waits for complete fact coverage and final prose', async ({ page }) => {
  test.setTimeout(100_000)
  await page.goto('/')

  const featured = page.getByRole('link', { name: '打开比赛', exact: true }).first()
  await expect(featured).toBeVisible({ timeout: 15_000 })
  await featured.click()
  await expect(page.locator('#match')).toBeVisible({ timeout: 15_000 })

  const input = page.getByLabel('向 Tennix 询问本场比赛')
  await input.fill('根据当前比赛的每盘技术统计详细信息，分析趋势和原因，并大胆预测谁能获胜。')
  await input.press('Enter')
  await expect(page.getByText(/正在(?:锁定比赛快照|拆解问题|读取比赛数据|组织回答)…/).first()).toBeVisible({
    timeout: 10_000,
  })

  const answer = await waitForCompleteAnswer(page)
  expect(answer).toMatch(/趋势|统计|预测|暂未提供/)
})
