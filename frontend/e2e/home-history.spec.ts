import { expect, test, type Page } from '@playwright/test'

/**
 * T54 Home player-history answer states.
 *
 * Functional coverage intercepts the Home Chat SSE route with deterministic
 * multi-frame payloads (including the controlled mixed empty/non-empty case).
 * The visual state captures the two dedicated T54 baselines (desktop 1440×1000
 * and mobile 390×844) without touching any existing approved snapshot.
 */

const freshness = {
  provider: 'fake',
  source_updated_at: null,
  observed_at: '2026-09-12T10:00:00Z',
  is_stale: false,
  age_seconds: 120,
}

const slateMatch = {
  id: 'mat_home_slate',
  status: 'scheduled',
  players: [
    { id: 'ply_home_sinner', name: 'Jannik Sinner', country_code: 'ita', ranking: 1 },
    { id: 'ply_home_alcaraz', name: 'Carlos Alcaraz', country_code: 'esp', ranking: 2 },
  ],
  tournament: { id: 'trn_home', name: 'ATP Finals', tour: 'atp' },
  scheduled_at: '2026-09-13T12:30:00Z',
  round: 'Semifinal',
  surface: 'hard',
  indoor: true,
  format: 'BO3',
  live_state: null,
  winner_player_id: null,
  freshness,
}

function catalog(status: 'live' | 'upcoming') {
  return {
    status,
    matches: [slateMatch],
    filters: { circuits: ['atp', 'wta'], genders: [], disciplines: ['singles'] },
    facet_counts: {
      circuits: { atp: 1, wta: 1, challenger: 0, itf: 0, other: 0 },
      genders: { men: 1, women: 0, mixed: 0, unknown: 0 },
      disciplines: { singles: 1, doubles: 0, team: 0, unknown: 0 },
    },
    featured_match_id: slateMatch.id,
  }
}

const sinner = {
  id: 'ply_hist_sinner',
  name: 'Jannik Sinner',
  country_code: 'ita',
  ranking: 1,
  localized_name: '辛纳',
}
const zheng = {
  id: 'ply_hist_zheng',
  name: 'Qinwen Zheng',
  country_code: 'chn',
  ranking: 5,
  localized_name: '郑钦文',
}

function finishedMatch(id: string, opponent: string, scheduledAt: string, score: unknown) {
  return {
    id,
    status: 'finished',
    players: [sinner, { id: `ply_opp_${opponent}`, name: opponent, country_code: 'esp', ranking: 2 }],
    tournament: { id: 'trn_hist', name: 'US Open', tour: 'atp' },
    scheduled_at: scheduledAt,
    round: 'Final',
    surface: 'hard',
    indoor: false,
    format: 'BO5',
    live_state: score,
    winner_player_id: sinner.id,
    freshness,
  }
}

function historyFrame(payload: Record<string, unknown>): string {
  return `event: data\ndata: ${JSON.stringify(payload)}`
}

function playerHistory(
  player: typeof sinner,
  scope: 'yesterday' | 'last' | 'recent' | 'season',
  options: {
    matches?: unknown[]
    season?: number | null
    seasonRecord?: unknown
    emptyReason?: 'no_results_in_scope' | 'season_record_unavailable' | null
    availability?: 'available' | 'partial' | 'unavailable' | 'stale'
  } = {},
) {
  return {
    kind: 'player_history',
    matches: options.matches ?? [],
    packet: null,
    resolution: null,
    player_history: {
      player,
      scope,
      season: options.season ?? null,
      availability: options.availability ?? 'available',
      season_record: options.seasonRecord ?? null,
      empty_reason: options.emptyReason ?? null,
    },
    metadata: {},
    answer_context: null,
  }
}

async function mockSlate(page: Page) {
  await page.route('**/api/matches/catalog**', (route) => {
    const status = new URL(route.request().url()).searchParams.get('status') as 'live' | 'upcoming'
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ data: catalog(status) }),
    })
  })
}

async function mockChatStream(page: Page, frames: string[]) {
  const body = [...frames, 'event: done\ndata: {"ok":true}', ''].join('\n\n')
  await page.route('**/api/chat/stream', (route) =>
    route.fulfill({
      status: 200,
      headers: { 'content-type': 'text/event-stream' },
      body,
    }),
  )
}

function watchErrors(page: Page) {
  const consoleErrors: string[] = []
  const pageErrors: string[] = []
  page.on('console', (message) => {
    if (message.type() === 'error') consoleErrors.push(message.text())
  })
  page.on('pageerror', (error) => pageErrors.push(error.message))
  return { consoleErrors, pageErrors }
}

async function ask(page: Page, question: string) {
  await page.getByLabel('向 Tennix 提问').fill(question)
  await page.getByLabel('向 Tennix 提问').press('Enter')
}

test.describe('Home history answer', () => {
  test('renders simultaneous multi-player sections with a controlled empty result', async ({ page }) => {
    const { consoleErrors, pageErrors } = watchErrors(page)
    await mockSlate(page)
    await mockChatStream(page, [
      'event: status\ndata: {"stage":"resolving"}',
      historyFrame(
        playerHistory(sinner, 'last', {
          matches: [
            finishedMatch('mat_hist_last', 'Carlos Alcaraz', '2026-08-20T10:00:00Z', null),
          ],
        }),
      ),
      historyFrame(
        playerHistory(zheng, 'recent', { emptyReason: 'no_results_in_scope' }),
      ),
      `event: text_delta\ndata: ${JSON.stringify({ delta: '辛纳上一场在 8 月 20 日获胜；郑钦文近期暂无赛果。' })}`,
    ])

    await page.goto('/')
    await ask(page, '辛纳上一次比赛是什么时候？郑钦文赛果如何？')

    await expect(page.getByRole('heading', { name: '球员赛果与战绩' })).toBeVisible()
    const sections = page.getByTestId('player-history-section')
    await expect(sections).toHaveCount(2)
    await expect(sections.nth(0)).toBeVisible()
    await expect(sections.nth(1)).toBeVisible()
    await expect(sections.nth(0)).toHaveAttribute('aria-label', 'Jannik Sinner（辛纳） 上一场比赛')
    await expect(sections.nth(1)).toHaveAttribute('aria-label', 'Qinwen Zheng（郑钦文） 近期赛果')

    // The empty player must not hide the other player's finished match.
    const openLink = sections.nth(0).getByRole('link', { name: /打开比赛：Sinner 对阵 Alcaraz/ })
    await expect(openLink).toBeVisible()
    await expect(openLink).toHaveAttribute('href', '/matches/mat_hist_last')
    await expect(sections.nth(1).getByText('该范围暂无赛果信息')).toBeVisible()

    // History answers never use the generic current-match empty title.
    await expect(page.getByText('没有符合条件的比赛')).toHaveCount(0)
    await expect(page.getByText('查询未完成')).toHaveCount(0)
    expect(consoleErrors.filter((text) => !text.includes('React DevTools'))).toEqual([])
    expect(pageErrors).toEqual([])
  })

  test('renders a season record section with only available surfaces', async ({ page }) => {
    await mockSlate(page)
    await mockChatStream(page, [
      historyFrame(
        playerHistory(zheng, 'season', {
          season: 2026,
          seasonRecord: {
            season: 2026,
            matches_won: 30,
            matches_lost: 5,
            titles: 4,
            hard: { won: 20, lost: 3 },
            clay: null,
            grass: { won: 10, lost: 2 },
          },
        }),
      ),
      `event: text_delta\ndata: ${JSON.stringify({ delta: '郑钦文本赛季 30 胜 5 负。' })}`,
    ])

    await page.goto('/')
    await ask(page, '郑钦文这个赛季战绩如何？')

    await expect(
      page.getByRole('heading', { name: 'Qinwen Zheng（郑钦文） · 2026 赛季战绩' }),
    ).toBeVisible()
    const summary = page.getByTestId('season-record-summary')
    await expect(summary).toBeVisible()
    await expect(summary).toContainText('86%')
    const surfaces = page.getByTestId('season-surface-record')
    await expect(surfaces).toHaveCount(2)
    await expect(summary).not.toContainText('红土')
    await expect(page.getByText('没有符合条件的比赛')).toHaveCount(0)
  })
})

test.describe('Home history visual', { tag: '@visual' }, () => {
  test('home-history-answer matches the current consumer UI', async ({ page }) => {
    await mockSlate(page)
    await mockChatStream(page, [
      historyFrame(
        playerHistory(sinner, 'recent', {
          matches: [
            finishedMatch('mat_hist_r1', 'Carlos Alcaraz', '2026-09-07T10:00:00Z', {
              score: {
                sets_won: [2, 0],
                sets: [
                  { number: 1, player1_games: 6, player2_games: 4 },
                  { number: 2, player1_games: 7, player2_games: 5 },
                ],
                points: [null, null],
                is_tiebreak: false,
              },
              server_player_id: null,
            }),
            finishedMatch('mat_hist_r2', 'Carlos Alcaraz', '2026-08-30T10:00:00Z', null),
          ],
        }),
      ),
      historyFrame(
        playerHistory(zheng, 'season', {
          season: 2026,
          seasonRecord: {
            season: 2026,
            matches_won: 30,
            matches_lost: 5,
            titles: 4,
            hard: { won: 20, lost: 3 },
            clay: { won: 8, lost: 2 },
            grass: null,
          },
        }),
      ),
      `event: text_delta\ndata: ${JSON.stringify({
        delta: '辛纳近期两场比赛均取胜；郑钦文本赛季 30 胜 5 负，共 4 个冠军。',
      })}`,
    ])

    await page.goto('/')
    await ask(page, '辛纳最近赛果如何？郑钦文这个赛季战绩如何？')

    await expect(page.getByRole('heading', { name: '球员赛果与战绩' })).toBeVisible()
    await expect(page.getByTestId('player-history-section')).toHaveCount(2)
    await expect(page.getByTestId('season-record-summary')).toBeVisible()
    // Hide the nondeterministic Next.js dev overlay host, matching the other suites.
    await page.addStyleTag({ content: 'nextjs-portal { display: none !important; }' })
    await page.evaluate(() => {
      window.scrollTo(0, 0)
      return document.fonts.ready
    })
    // Let the answer-triggered smooth scroll settle, then pin the viewport back
    // to the top so the baseline stays repeatable.
    await page.waitForTimeout(600)
    await page.evaluate(
      () =>
        new Promise((resolve) => {
          window.scrollTo({ top: 0, behavior: 'instant' })
          requestAnimationFrame(() => resolve(null))
        }),
    )
    await expect(page).toHaveScreenshot('home-history-answer.png', {
      animations: 'disabled',
      fullPage: true,
    })
  })
})
