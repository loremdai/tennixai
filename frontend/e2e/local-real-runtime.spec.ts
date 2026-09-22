// T80 opt-in browser acceptance for the launcher-run local real runtime.
//
// Runs ONLY when TENNIX_E2E_LOCAL_RUNTIME=1 and assumes the stack started by
// `./scripts/tennix-live up` is already serving (default origin
// http://127.0.0.1:3100; override with TENNIX_E2E_LOCAL_RUNTIME_URL):
//   TENNIX_E2E_LOCAL_RUNTIME=1 pnpm exec playwright test e2e/local-real-runtime.spec.ts
//
// Acceptance semantics (all honest, none assume a live match or a BUY exists):
//   * Home renders real catalog rows or the approved honest empty state;
//   * Players renders English primary / Chinese secondary names or an honest
//     coverage state ("排名暂不可用" panels);
//   * Match/Markets pages carry no preview fixture strings (the prototype is
//     gated behind ?preview= and renders exclusive markers);
//   * the Decision Workbench stays paper-only with no trading CTA;
//   * DOM and same-origin JSON responses never carry provider external IDs,
//     token material, wallet strings or credentials.

import { expect, test, type Page } from '@playwright/test'

const ENABLED = process.env.TENNIX_E2E_LOCAL_RUNTIME === '1'
const BASE_URL = process.env.TENNIX_E2E_LOCAL_RUNTIME_URL ?? 'http://127.0.0.1:3100'

// Same hygiene patterns as the T71 real shadow gate (e2e/p3-live.spec.ts).
const PROVIDER_PATTERNS = [
  /0x[0-9a-fA-F]{16,}/, // polymarket condition ids
  /\b\d{20,}\b/, // asset/token ids
  /wallet/i,
  /private[-_ ]key/i,
  /APIkey/i, // api-tennis query credential
]

// Markers rendered exclusively by the gated ?preview prototypes
// (components/p3/p3-preview-controls.tsx); they must never appear on the
// production pages served by the launcher stack.
const PREVIEW_MARKERS = ['仅用于原型', 'PREVIEW', '切换状态']

function assertNoProviderMaterial(text: string, url: string) {
  for (const pattern of PROVIDER_PATTERNS) {
    expect(text, `provider material ${pattern} in DOM`).not.toMatch(pattern)
    expect(url, `provider material ${pattern} in URL`).not.toMatch(pattern)
  }
}

async function scanPage(page: Page) {
  const body = await page.evaluate(() => document.body.innerText)
  assertNoProviderMaterial(body, page.url())
  expect(page.url(), 'production pages never carry a preview query').not.toContain(
    'preview',
  )
  for (const marker of PREVIEW_MARKERS) {
    expect(body, `preview marker ${marker} on production page`).not.toContain(marker)
  }
}

/** Scans same-origin JSON response bodies for provider material. */
function watchNetwork(page: Page) {
  const violations: string[] = []
  page.on('response', (response) => {
    const url = response.url()
    if (!url.startsWith(BASE_URL)) return
    const contentType = response.headers()['content-type'] ?? ''
    if (!contentType.includes('application/json')) return
    response
      .text()
      .then((body) => {
        for (const pattern of PROVIDER_PATTERNS) {
          if (pattern.test(body)) {
            violations.push(`${new URL(url).pathname} matched ${pattern}`)
          }
        }
      })
      .catch(() => {
        /* body unreadable (already consumed/streamed): nothing to scan */
      })
  })
  return {
    assertClean() {
      expect(violations, 'provider material in API JSON responses').toEqual([])
    },
  }
}

async function resolveRowsOrEmpty(page: Page, emptyPattern: RegExp) {
  const rows = page.locator('a[href^="/matches/"]')
  const hasRows = await rows
    .first()
    .waitFor({ state: 'visible', timeout: 20_000 })
    .then(() => true)
    .catch(() => false)
  if (hasRows) {
    await expect(rows.first()).toBeVisible()
  } else {
    // Approved honest empty state; never fabricated rows.
    await expect(page.getByText(emptyPattern).first()).toBeVisible()
  }
  return hasRows
}

test.describe('T80 local real runtime browser acceptance', () => {
  test.skip(!ENABLED, 'TENNIX_E2E_LOCAL_RUNTIME not set')

  // Guard against a false pass: these assertions can only be trusted when the
  // launcher-run REAL backend is serving. A fake-mode frontend would render
  // plausible pages too, so before any UI check we require the backend's own
  // runtime health to report state "ok", fetched through the same origin the
  // spec already uses (the frontend proxies /api/runtime/health to the
  // backend's /api/v1/runtime/health). If this fails, the stack was not
  // started via the live launcher.
  test.beforeAll(async () => {
    if (!ENABLED) return
    const hint =
      'real runtime not healthy at ' +
      `${BASE_URL}/api/runtime/health — start the launcher stack with ` +
      '`./scripts/tennix-live up` before running this opt-in gate'
    let body: { state?: string } | null = null
    try {
      const response = await fetch(`${BASE_URL}/api/runtime/health`)
      if (response.ok) {
        body = (await response.json()) as { state?: string }
      }
    } catch {
      body = null
    }
    expect(body?.state, hint).toBe('ok')
  })

  test('home renders real catalog data or the honest empty state', async ({ page }) => {
    const network = watchNetwork(page)
    await page.goto(`${BASE_URL}/`)
    await page.waitForTimeout(2500)
    await scanPage(page)
    await resolveRowsOrEmpty(page, /暂无|没有|无比赛/)
    network.assertClean()
  })

  test('players renders bilingual names or an honest coverage state', async ({
    page,
  }) => {
    const network = watchNetwork(page)
    await page.goto(`${BASE_URL}/players`)
    await page.waitForTimeout(2500)
    await scanPage(page)

    const links = page.locator('a[href^="/players/"]')
    const hasRows = await links
      .first()
      .waitFor({ state: 'visible', timeout: 20_000 })
      .then(() => true)
      .catch(() => false)

    if (!hasRows) {
      // Honest coverage state: rankings unavailable / directory empty / load
      // failure panels are all approved factual outcomes.
      await expect(
        page.getByText(/排名暂不可用|还没有可用|加载失败/).first(),
      ).toBeVisible()
    } else {
      const labels = await links.evaluateAll((elements) =>
        elements.map(
          (element) =>
            element.getAttribute('aria-label') ?? element.textContent ?? '',
        ),
      )
      const cjk = /[一-鿿]/
      const bilingual = labels.filter((label) => {
        const inner = label.replace(/^查看\s*/, '').replace(/\s*的球员资料$/, '')
        const [primary, secondary] = inner.split('，')
        return (
          primary !== undefined &&
          secondary !== undefined &&
          /[A-Za-z]/.test(primary) &&
          cjk.test(secondary)
        )
      })
      expect(
        bilingual.length,
        'English primary / Chinese secondary names expected (init enrichment)',
      ).toBeGreaterThan(0)
    }
    network.assertClean()
  })

  test('markets and match workbench are production, paper-only and preview-free', async ({
    page,
  }) => {
    const network = watchNetwork(page)
    await page.goto(`${BASE_URL}/markets`)
    await page.waitForTimeout(2000)
    await scanPage(page)

    const firstRow = page.locator('a[href^="/matches/"]').first()
    const emptyTab = !(await firstRow
      .waitFor({ state: 'visible', timeout: 20_000 })
      .then(() => true)
      .catch(() => false))
    if (emptyTab) {
      // The opportunities tab explains itself with the product's own honest
      // reason (an unpromoted model, nothing passing the gate, …), never a
      // fabricated opportunity. Its CTA reaches every market, where mapped
      // rows carry the real quotes this acceptance still has to exercise.
      await expect(
        page.getByRole('heading', {
          name: /模型尚未完成验证|当前没有机会|暂无可评估市场|决策数据恢复中|暂无符合门槛的机会/,
        }),
      ).toBeVisible()
      await page.getByRole('button', { name: '查看全部市场' }).click()
      await page.waitForTimeout(2500)
      await scanPage(page)
    }

    const mappedRow = page.locator('a[href^="/matches/"]').first()
    if ((await mappedRow.count()) === 0) {
      // Honest quiet market: no mapped rows right now. Annotate instead of
      // fabricating a match flow.
      test.info().annotations.push({
        type: 'local-runtime-note',
        description: `no mapped market rows on ${new Date().toISOString()}; match workbench not exercised`,
      })
      network.assertClean()
      return
    }

    await mappedRow.click()
    await page.waitForTimeout(2500)
    await scanPage(page)

    // Decision Workbench is paper-only: no trading CTA, no real-money copy.
    await expect(
      page.getByRole('button', { name: /BUY|SELL|下单|买入|卖出/ }),
    ).toHaveCount(0)
    const body = await page.evaluate(() => document.body.innerText)
    for (const banned of ['充值', '入金', '提现', '实盘', 'Deposit', 'withdraw']) {
      expect(body, `real-money copy ${banned} on workbench`).not.toContain(banned)
    }
    network.assertClean()
  })
})
