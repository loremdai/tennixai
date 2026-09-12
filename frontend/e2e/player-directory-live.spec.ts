import { expect, test, type Page } from '@playwright/test'

/**
 * Bounded live gate for the production player pages against the real
 * API-Tennis directory (webServer runs with TENNIX_PROVIDER_MODE=api_tennis
 * when TENNIX_E2E_API_TENNIS=1 and a key exists in the root .env).
 * Chat journey items additionally require TENNIX_E2E_REAL_LLM=1.
 * Skipped honestly in every other environment; never updates snapshots.
 */

test.skip(
  process.env.TENNIX_E2E_API_TENNIS !== '1',
  'player-directory-live requires TENNIX_E2E_API_TENNIS=1',
)

const FORBIDDEN_PAYLOAD = /player_key|first_player_key|second_player_key|event_key|api_key|Bearer\s/i

function watchPage(page: Page) {
  const consoleErrors: string[] = []
  const payloadHits: string[] = []
  page.on('console', (message) => {
    if (message.type() === 'error') consoleErrors.push(message.text())
  })
  page.on('response', async (response) => {
    if (!response.url().includes('/api/players')) return
    const body = await response.text().catch(() => '')
    if (FORBIDDEN_PAYLOAD.test(body)) payloadHits.push(response.url())
  })
  return { consoleErrors, payloadHits }
}

async function waitForChatCompletion(page: Page) {
  const assistant = page.locator('#assistant')
  await expect(assistant.getByRole('button', { name: '发送问题' })).toBeEnabled({ timeout: 120_000 })
  await expect(assistant).not.toContainText('查询失败', { timeout: 5_000 })
}

test('live directory - official rankings, WTA switch and China filter', async ({ page }) => {
  const { consoleErrors, payloadHits } = watchPage(page)

  await page.goto('/players')
  await expect(page.getByRole('heading', { name: 'ATP 单打世界排名' })).toBeVisible({ timeout: 60_000 })
  const atpRows = page.getByRole('region', { name: 'ATP 世界排名列表' }).getByRole('listitem')
  await expect(atpRows.first()).toBeVisible({ timeout: 60_000 })
  expect(await atpRows.count()).toBe(50)
  await expect(page.getByText(/共 \d+ 位/)).toBeVisible()

  await page.getByRole('tab', { name: 'WTA' }).click()
  await expect(page.getByRole('heading', { name: 'WTA 单打世界排名' })).toBeVisible({ timeout: 60_000 })
  const wtaRows = page.getByRole('region', { name: 'WTA 世界排名列表' }).getByRole('listitem')
  await expect(wtaRows.first()).toBeVisible({ timeout: 60_000 })

  await page.getByRole('button', { name: '仅看中国球员' }).click()
  const chnRows = page.getByRole('region', { name: 'WTA 世界排名列表' }).getByRole('listitem')
  await expect(chnRows.first()).toBeVisible({ timeout: 60_000 })
  const total = await chnRows.count()
  expect(await chnRows.filter({ hasText: 'CHN' }).count()).toBe(total)

  expect(payloadHits).toEqual([])
  expect(consoleErrors.filter((text) => !text.includes('React DevTools'))).toEqual([])
})

test('live directory - Chinese search resolves Ben Shelton and opens the profile', async ({ page }) => {
  const { payloadHits } = watchPage(page)

  await page.goto('/players')
  await expect(page.getByRole('heading', { name: 'ATP 单打世界排名' })).toBeVisible({ timeout: 60_000 })
  await page.locator('#player-directory-search').fill('谢尔顿')
  await page.locator('#player-directory-search').press('Enter')

  const shelton = page.getByRole('link', { name: /Ben Shelton/ }).first()
  await expect(shelton).toBeVisible({ timeout: 60_000 })
  await shelton.click()

  await expect(page.getByRole('heading', { level: 1, name: 'Ben Shelton' })).toBeVisible({ timeout: 60_000 })
  await expect(page.getByRole('heading', { name: '赛季摘要' })).toBeVisible({ timeout: 60_000 })
  await expect(page.getByRole('heading', { name: '当前比赛状态' })).toBeVisible()

  expect(payloadHits).toEqual([])
})

test('live directory - season filters, pagination and finished match navigation', async ({ page }) => {
  const { payloadHits } = watchPage(page)

  await page.goto('/players')
  await expect(page.getByRole('heading', { name: 'ATP 单打世界排名' })).toBeVisible({ timeout: 60_000 })
  await page.locator('#player-directory-search').fill('Ben Shelton')
  await page.locator('#player-directory-search').press('Enter')
  await page.getByRole('link', { name: /Ben Shelton/ }).first().click()
  await expect(page.getByRole('heading', { level: 1, name: 'Ben Shelton' })).toBeVisible({ timeout: 60_000 })

  const results = page.getByRole('region', { name: 'Ben Shelton 历史赛果列表' })
  await expect(results).toBeVisible({ timeout: 60_000 })
  const footer = page.getByText(/1–20 \/ 共 \d+ 场/)
  await expect(footer).toBeVisible({ timeout: 60_000 })

  const next = page.getByRole('button', { name: '下一页' }).last()
  if (await next.isEnabled()) {
    await next.click()
    await expect(page.getByText(/21–\d+ \/ 共 \d+ 场/)).toBeVisible({ timeout: 60_000 })
    await page.getByRole('button', { name: '上一页' }).last().click()
  }

  await page.getByRole('button', { name: '赛果：全部结果' }).click()
  await page.getByRole('menuitem', { name: '胜' }).click()
  await expect(results.getByText('负', { exact: true })).toHaveCount(0, { timeout: 60_000 })

  await results.getByRole('link').first().click()
  await page.waitForURL(/\/matches\/[^/]+$/, { timeout: 60_000 })

  expect(payloadHits).toEqual([])
})

test.describe('live directory - Home/Match chat journey', () => {
  test.skip(
    process.env.TENNIX_E2E_REAL_LLM !== '1',
    'chat journey items require TENNIX_E2E_REAL_LLM=1',
  )

  const questions = [
    'Ben Shelton 下一场什么时候？',
    'Shelton 今天有比赛吗？',
    '谢尔顿现在比分多少？',
    '郑钦文这个赛季战绩如何？',
  ]

  for (const question of questions) {
    test(`home question completes: ${question}`, async ({ page }) => {
      await page.goto('/')
      await page.getByLabel('继续向 Tennix 提问').fill(question)
      await page.getByLabel('继续向 Tennix 提问').press('Enter')
      await waitForChatCompletion(page)
    })
  }

  test('ambiguous surname ends with candidates and done', async ({ page }) => {
    await page.goto('/')
    await page.getByLabel('继续向 Tennix 提问').fill('Wang 最近战绩如何？')
    await page.getByLabel('继续向 Tennix 提问').press('Enter')
    await waitForChatCompletion(page)
    await expect(page.getByText('多位候选球员，请选择')).toBeVisible({ timeout: 5_000 })
  })

  test('match chat answers Shelton serve questions in match context', async ({ page }) => {
    await page.goto('/')
    await page.getByLabel('继续向 Tennix 提问').fill('谢尔顿现在比分多少？')
    await page.getByLabel('继续向 Tennix 提问').press('Enter')
    await waitForChatCompletion(page)

    const card = page.getByRole('link', { name: /打开比赛：/ }).first()
    if (!(await card.isVisible().catch(() => false))) {
      test.info().annotations.push({
        type: 'note',
        description: 'no Shelton match card currently offered; match chat covered by deterministic gates',
      })
      return
    }
    await card.click()
    await page.getByLabel('继续就这场比赛提问').fill('Shelton 现在在发球吗？')
    await page.getByLabel('继续就这场比赛提问').press('Enter')
    await waitForChatCompletion(page)
  })
})
