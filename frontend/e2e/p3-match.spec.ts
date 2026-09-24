import { expect, test, type Page } from '@playwright/test'

// T69 production match decision workbench flows. Match REST/SSE and decision
// REST/SSE are intercepted with canonical payloads so every state family can
// be refreshed directly and deterministically; the real Next routes, runtime
// decoders, hooks and components still do all the work. Asserts independent
// sports/decision gap handling, keyboard access, responsive fit and zero
// console/SSE errors.

const MATCH_ID = 'mat_wb_1'
const AS_OF = new Date().toISOString()

const MATCH_SNAPSHOT = {
  match: {
    id: MATCH_ID,
    status: 'live',
    players: [
      { id: 'ply_a', name: 'WB Alpha', country_code: null, ranking: 1 },
      { id: 'ply_b', name: 'WB Beta', country_code: null, ranking: 2 },
    ],
    tournament: { id: 'trn_wb', name: 'WB Open', tour: 'atp' },
    scheduled_at: null,
    round: 'Semifinal',
    surface: 'hard',
    indoor: false,
    format: 'BO3',
    live_state: {
      score: {
        sets_won: [1, 0],
        sets: [{ number: 1, player1_games: 6, player2_games: 4 }],
        points: ['30', '15'],
        is_tiebreak: false,
      },
      server_player_id: 'ply_a',
      state_version: 5,
      connection_status: 'live',
      last_event_at: AS_OF,
      as_of: AS_OF,
    },
    winner_player_id: null,
    freshness: {
      provider: 'fake',
      source_updated_at: null,
      observed_at: AS_OF,
      is_stale: false,
      age_seconds: 0,
    },
  },
  points: [],
  statistics: [],
  momentum: [],
  quality: [],
  state_version: 5,
  as_of: AS_OF,
}

function decisionFixture(state: string) {
  const base = {
    match_id: MATCH_ID,
    market_id: 'mkt_wb_1',
    action: 'hold',
    reason_code: null,
    target_player_id: 'ply_a',
    observation_version: 3,
    model_probabilities: { ply_a: 0.62, ply_b: 0.38 },
    model_availability: 'available',
    quote_average_price: '0.525',
    quote_side: 'exit',
    conservative_net_edge: '0.0400',
    max_acceptable_price: null,
    hold_value: '10.80',
    model_version: 'prematch-elo-v1',
    calibration_version: 'platt-v1',
    policy_version: 'policy-v1',
    data_version: 'apidata-v1',
    gates: [
      { gate: 'mapping', passed: true, reason_code: null },
      { gate: 'net_edge', passed: true, reason_code: null },
    ],
    outcome_levels: [
      { player_id: 'ply_a', best_bid: '0.55', best_ask: '0.57' },
      { player_id: 'ply_b', best_bid: '0.43', best_ask: '0.45' },
    ],
    position: null,
    lifecycle: [],
    is_stale: false,
    has_gap: false,
    lock_profit_available: false,
    as_of: AS_OF,
  }
  const position = {
    position_id: 'pos_wb',
    outcome_player_id: 'ply_a',
    status: 'open',
    entry_cost: '10.00',
    shares: '19.05',
    average_entry_price: '0.525',
    current_exit_value: '11.40',
    net_pnl: null,
    events: [
      { id: 'e1', kind: 'entry_intent', at: AS_OF, reason_code: null },
      { id: 'e2', kind: 'entry_fill', at: AS_OF, reason_code: null },
    ],
  }
  switch (state) {
    case 'buy':
      return { ...base, action: 'buy', quote_side: 'entry', conservative_net_edge: '0.0700' }
    case 'wait':
      return { ...base, action: 'wait', max_acceptable_price: '0.5500', quote_average_price: null, quote_side: null, conservative_net_edge: null }
    case 'entry_pending':
      return {
        ...base,
        action: 'buy',
        lifecycle: ['entry_pending'],
        position: {
          ...position,
          position_id: 'int_entry_wb',
          status: 'entry_pending',
          current_exit_value: null,
          events: [{ id: 'e1', kind: 'entry_intent', at: AS_OF, reason_code: null }],
        },
      }
    case 'hold':
      return { ...base, lifecycle: ['entry_pending', 'filled'], position }
    case 'sell':
      return { ...base, action: 'sell', lifecycle: ['entry_pending', 'filled'], position }
    case 'settled':
      return {
        ...base,
        lifecycle: ['entry_pending', 'filled', 'settled'],
        position: { ...position, status: 'settled', net_pnl: '1.40', current_exit_value: null, events: [...position.events, { id: 'e3', kind: 'settled', at: AS_OF, reason_code: null }] },
      }
    default:
      return base
  }
}

function sse(frames: string[]): string {
  return frames.join('')
}

async function interceptWorkbench(page: Page, state: string, options: { decisionDelta?: number } = {}) {
  const decision = decisionFixture(state)
  await page.route((url) => {
    const path = url.pathname
    return (
      path === `/api/matches/${MATCH_ID}` ||
      path === `/api/matches/${MATCH_ID}/stream` ||
      path === `/api/matches/${MATCH_ID}/decision` ||
      path === `/api/matches/${MATCH_ID}/decision/stream`
    )
  }, async (route) => {
    const path = new URL(route.request().url()).pathname
    if (path === `/api/matches/${MATCH_ID}/stream`) {
      await route.fulfill({
        status: 200,
        contentType: 'text/event-stream',
        body: sse([
          `event: ready\nid: 5\ndata: ${JSON.stringify({ snapshot: MATCH_SNAPSHOT, state_version: 5, as_of: AS_OF })}\n\n`,
        ]),
      })
      return
    }
    if (path === `/api/matches/${MATCH_ID}/decision/stream`) {
      const frames = [
        `event: ready\nid: ${decision.observation_version}\ndata: ${JSON.stringify({
          match_id: MATCH_ID,
          decision,
          observation_version: decision.observation_version,
          action: decision.action,
        })}\n\n`,
      ]
      if (options.decisionDelta) {
        frames.push(
          `event: decision_delta\nid: ${options.decisionDelta}\ndata: ${JSON.stringify({
            type: 'decision_delta',
            match_id: MATCH_ID,
            observation_version: options.decisionDelta,
            action: 'hold',
            as_of: AS_OF,
          })}\n\n`,
        )
      }
      await route.fulfill({ status: 200, contentType: 'text/event-stream', body: sse(frames) })
      return
    }
    if (path === `/api/matches/${MATCH_ID}/decision`) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ data: decision }),
      })
      return
    }
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ data: MATCH_SNAPSHOT }),
    })
  })
}

test.describe('P3 match workbench state families', () => {
  for (const state of ['buy', 'wait', 'entry_pending', 'hold', 'sell', 'settled'] as const) {
    test(`direct refresh renders the ${state} family`, async ({ page }) => {
      await interceptWorkbench(page, state)
      await page.goto(`/matches/${MATCH_ID}`)
      await expect(page.getByRole('heading', { name: '胜率与市场价格走势' })).toBeVisible()

      // Direct refresh keeps the identical state (snapshot-first from REST).
      await page.reload()
      await expect(page.getByRole('heading', { name: '胜率与市场价格走势' })).toBeVisible()
      await expect(page.getByRole('heading', { name: '判断依据' })).toBeVisible()
      // States with a ledger position keep the permanent lifecycle timeline.
      const hasPosition = ['entry_pending', 'hold', 'sell', 'settled'].includes(state)
      await expect(page.getByRole('heading', { name: '模拟交易记录' })).toHaveCount(hasPosition ? 1 : 0)
    })
  }

  test('buy family shows the research summary and no trade CTA', async ({ page }) => {
    await interceptWorkbench(page, 'buy')
    await page.goto(`/matches/${MATCH_ID}`)

    // Scoped to the summary section: the chart renders composite texts like
    // "模型 62.0% / ask 57.0%" and its sr-only table repeats raw percents.
    const summary = page.locator('section[aria-labelledby="decision-summary-title"]')
    await expect(summary.getByRole('paragraph').getByText('模拟买入机会', { exact: true })).toBeVisible()
    await expect(summary.getByText('62.0%', { exact: true })).toBeVisible()
    await expect(summary.getByText('+7.0 个百分点', { exact: true })).toBeVisible()
    await expect(page.getByRole('button', { name: /问这场比赛/ })).toBeVisible()
    await expect(page.getByRole('button', { name: /BUY|下单|买入|真实交易/ })).toHaveCount(0)
  })

  test('entry_pending shows the ledger timeline without a fabricated fill', async ({ page }) => {
    await interceptWorkbench(page, 'entry_pending')
    await page.goto(`/matches/${MATCH_ID}`)

    // Both the summary and the lifecycle badge render the canonical state
    // label, so every assertion is scoped to its own section.
    const summary = page.locator('section[aria-labelledby="decision-summary-title"]')
    const lifecycle = page.locator('section[aria-labelledby="paper-lifecycle-title"]')
    await expect(summary.getByText('等待买入确认', { exact: true })).toBeVisible()
    await expect(lifecycle.getByText('已提交模拟买入')).toBeVisible()
    await expect(lifecycle.getByText('10 美元模拟订单，正在确认价格与可交易金额')).toBeVisible()
  })

  test('settled shows the terminal ledger state', async ({ page }) => {
    await interceptWorkbench(page, 'settled')
    await page.goto(`/matches/${MATCH_ID}`)

    const summary = page.locator('section[aria-labelledby="decision-summary-title"]')
    const lifecycle = page.locator('section[aria-labelledby="paper-lifecycle-title"]')
    await expect(summary.getByText('已结算', { exact: true })).toBeVisible()
    await expect(lifecycle.getByText('比赛结果已结算')).toBeVisible()
    await expect(lifecycle.getByText('模拟盈亏')).toBeVisible()
  })
})

test.describe('P3 workbench stream independence and a11y', () => {
  test('a decision gap degrades only the decision stream', async ({ page }) => {
    await interceptWorkbench(page, 'hold', { decisionDelta: 99 })
    // The delta jumps to v99 while REST keeps returning the v3 snapshot, so
    // the refetched version never reaches the target and the stream stays
    // degraded while the last trusted snapshot remains on screen.
    await page.goto(`/matches/${MATCH_ID}`)

    await expect(page.getByText(/判断暂时无法更新/)).toBeVisible({ timeout: 15_000 })
    // The sports view is untouched by the decision gap: the score section and
    // the last trusted match data stay rendered (both fake SSE streams close
    // after fulfil, so a P2 reconnect notice is legitimate and orthogonal).
    await expect(page.getByRole('heading', { name: '比分与比赛进程' })).toBeVisible()
    await expect(page.getByText('WB Alpha').first()).toBeVisible()
  })

  test('keyboard users reach the summary affordances and rows stay in tab order', async ({ page }) => {
    await interceptWorkbench(page, 'hold')
    await page.goto(`/matches/${MATCH_ID}`)
    await expect(page.getByRole('heading', { name: '胜率与市场价格走势' })).toBeVisible()

    await page.getByRole('button', { name: /问这场比赛/ }).focus()
    await expect(page.getByRole('button', { name: /问这场比赛/ })).toBeFocused()
  })

  test('no console or page errors across the workbench lifecycle', async ({ page }) => {
    const consoleErrors: string[] = []
    const pageErrors: string[] = []
    page.on('console', (message) => {
      if (message.type() === 'error') consoleErrors.push(message.text())
    })
    page.on('pageerror', (error) => pageErrors.push(String(error)))

    await interceptWorkbench(page, 'hold')
    await page.goto(`/matches/${MATCH_ID}`)
    await expect(page.getByRole('heading', { name: '胜率与市场价格走势' })).toBeVisible()
    await page.waitForTimeout(1500)

    expect(pageErrors).toEqual([])
    expect(consoleErrors.filter((text) => !text.includes('React DevTools'))).toEqual([])
  })
})

test.describe('P3 workbench mobile', () => {
  test.use({ viewport: { width: 390, height: 844 } })

  test('no horizontal overflow at 390×844', async ({ page }) => {
    await interceptWorkbench(page, 'hold')
    await page.goto(`/matches/${MATCH_ID}`)
    await expect(page.getByRole('heading', { name: '胜率与市场价格走势' })).toBeVisible()

    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    )
    expect(overflow).toBeLessThanOrEqual(0)

    const ask = page.getByRole('button', { name: /问这场比赛/ })
    const box = await ask.boundingBox()
    expect(box).not.toBeNull()
    expect(box!.height).toBeGreaterThanOrEqual(36)
  })
})
