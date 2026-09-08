import { expect, test } from '@playwright/test'

test.describe('P1 flow', () => {
  test('home question renders a structured card that opens the internal match page', async ({ page }) => {
    await page.goto('/')
    await page.getByLabel('继续向 Tennix 提问').fill('Sinner 今晚几点比赛？')
    await page.getByLabel('继续向 Tennix 提问').press('Enter')

    const card = page.getByRole('link', { name: /打开比赛：Sinner 对阵/ }).first()
    await expect(card).toBeVisible()
    const href = await card.getAttribute('href')
    expect(href).toMatch(/^\/matches\/mat_/)

    await card.click()
    await expect(page.getByRole('heading', { name: /Sinner/ }).first()).toBeVisible()
    await expect(page.getByText('P2 数据暂不可用').first()).toBeVisible()
  })

  test('match page answers a contextual question without repeating the match', async ({ page }) => {
    await page.goto('/')
    const featured = page.getByRole('link', { name: '打开比赛', exact: true })
    await expect(featured).toBeVisible()
    await featured.click()

    await page.getByLabel('向 Tennix 询问本场比赛').fill('谁在发球？')
    await page.getByLabel('向 Tennix 询问本场比赛').press('Enter')

    await expect(page.getByText('已获取本场比赛的结构化数据。')).toBeVisible()
    const serverIndicator = page.locator('#server-indicator')
    await expect(serverIndicator).toBeVisible()
  })

  test('explicit refresh reloads match data', async ({ page }) => {
    await page.goto('/')
    const featured = page.getByRole('link', { name: '打开比赛', exact: true })
    await expect(featured).toBeVisible()

    const requests: string[] = []
    page.on('request', (request) => {
      if (/\/api\/matches\/mat_/.test(request.url())) requests.push(request.url())
    })
    await featured.click()
    await expect(page.locator('#match')).toBeVisible()

    const refresh = page.getByRole('button', { name: '刷新比赛数据' })
    await expect(refresh).toBeVisible()
    await refresh.click()
    await expect(page.locator('#match')).toBeVisible()
    expect(requests.length).toBeGreaterThanOrEqual(2)
  })

  test('historical question returns typed unsupported without a card', async ({ page }) => {
    await page.goto('/')
    await page.getByLabel('继续向 Tennix 提问').fill('昨天 Sinner 赢了吗？')
    await page.getByLabel('继续向 Tennix 提问').press('Enter')

    await expect(page.getByText('P1 暂不支持历史比赛结果查询。')).toBeVisible()
    await expect(page.getByRole('link', { name: /打开比赛：/ }).first()).toBeHidden()
  })

  test('provider failure renders typed retry copy on home', async ({ page }) => {
    await page.route('**/api/matches*', (route) => {
      if (route.request().url().includes('/api/matches?')) {
        return route.fulfill({
          status: 503,
          contentType: 'application/json',
          body: JSON.stringify({
            error: { code: 'provider_unavailable', message: 'LiveTennisAPI request failed', details: {} },
            request_id: 'req-test',
          }),
        })
      }
      return route.continue()
    })

    await page.goto('/')
    await expect(page.getByText(/比赛数据加载失败（provider_unavailable）/)).toBeVisible()
    await expect(page.getByRole('button', { name: '重试加载比赛数据' })).toBeVisible()
  })
})
