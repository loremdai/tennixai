export type TourKey = 'ATP' | 'WTA'
export type MovementDirection = 'up' | 'down' | 'flat'
export type ProfileStatusKey = 'live' | 'next' | 'none'
export type PlayerHistoryState =
  | 'ready'
  | 'empty'
  | 'partial'
  | 'unavailable'
  | 'loading'
  | 'error'
  | 'stale'
export type CompetitionTier = TourKey | 'Challenger' | 'ITF'
export type MatchOutcome = 'win' | 'loss'

export type RankMovement = {
  direction: MovementDirection
  places: number
}

export type CountryPreview = {
  code: string
  name: string
  flagUrl: string | null
}

export type PlayerDirectoryEntry = {
  id: string
  tour: TourKey
  name: string
  nameZh: string | null
  shortName: string
  countryCode: string
  countryName: string
  flagUrl: string | null
  rank: number | null
  points: number | null
  movement: RankMovement
  avatarUrl: string | null
  aliases: string[]
}

export type PlayerProfilePreview = PlayerDirectoryEntry & {
  birthDate: string | null
  age: number | null
  rankUpdatedAt: string
}

export type PlayerSeasonSummaryPreview = {
  season: number
  matches: number | null
  wins: number | null
  losses: number | null
  winRate: number | null
  titles: number | null
  hardWinRate: number | null
  clayWinRate: number | null
  grassWinRate: number | null
}

export type PlayerResultPreview = {
  id: string
  matchId: string
  season: number
  date: string
  tournament: string
  tournamentZh: string
  tier: CompetitionTier
  surface: '硬地' | '红土' | '草地'
  round: string
  opponent: {
    name: string
    nameZh: string | null
    countryCode: string
    countryName: string
    flagUrl: string | null
  }
  outcome: MatchOutcome
  score: string
}

export type PlayerCurrentStatusPreview =
  | {
      kind: 'live'
      matchId: string
      event: string
      round: string
      opponent: PlayerResultPreview['opponent']
      score: string
      detail: string
      freshness: string
    }
  | {
      kind: 'next'
      matchId: string
      event: string
      round: string
      opponent: PlayerResultPreview['opponent']
      startLabel: string
      countdown: string
    }
  | {
      kind: 'none'
      message: string
    }

export type PlayerProfileScenario = {
  profile: PlayerProfilePreview
  seasonSummaries: PlayerSeasonSummaryPreview[]
  results: PlayerResultPreview[]
  defaultStatus: ProfileStatusKey
  defaultHistoryState: PlayerHistoryState
}

export type PlayerProfileBundle = {
  currentPlayerId: string
  scenarios: PlayerProfileScenario[]
}

const countrySeeds = [
  ['ITA', '意大利'],
  ['ESP', '西班牙'],
  ['DEU', '德国'],
  ['SRB', '塞尔维亚'],
  ['USA', '美国'],
  ['AUS', '澳大利亚'],
  ['GBR', '英国'],
  ['DNK', '丹麦'],
  ['NOR', '挪威'],
  ['GRC', '希腊'],
  ['POL', '波兰'],
  ['BLR', '白俄罗斯'],
  ['KAZ', '哈萨克斯坦'],
  ['CHN', '中国'],
  ['JPN', '日本'],
  ['CAN', '加拿大'],
  ['FRA', '法国'],
  ['BEL', '比利时'],
  ['NLD', '荷兰'],
  ['CZE', '捷克'],
  ['CHE', '瑞士'],
  ['ARG', '阿根廷'],
  ['BRA', '巴西'],
  ['HKG', '中国香港'],
] as const

const alpha2CountryCodes: Record<string, string> = {
  ITA: 'it',
  ESP: 'es',
  DEU: 'de',
  SRB: 'rs',
  USA: 'us',
  AUS: 'au',
  GBR: 'gb',
  DNK: 'dk',
  NOR: 'no',
  GRC: 'gr',
  POL: 'pl',
  BLR: 'by',
  KAZ: 'kz',
  CHN: 'cn',
  JPN: 'jp',
  CAN: 'ca',
  FRA: 'fr',
  BEL: 'be',
  NLD: 'nl',
  CZE: 'cz',
  CHE: 'ch',
  ARG: 'ar',
  BRA: 'br',
  HKG: 'hk',
}

function flagUrl(code: string) {
  const alpha2Code = alpha2CountryCodes[code]
  return alpha2Code ? `https://flagcdn.com/w40/${alpha2Code}.png` : null
}

const countryByCode = Object.fromEntries(
  countrySeeds.map(([code, name]) => [code, { code, name, flagUrl: flagUrl(code) }]),
) as Record<string, CountryPreview>

export const PLAYER_COUNTRY_OPTIONS = countrySeeds.map(([code]) => countryByCode[code])

function country(code: string) {
  return countryByCode[code] ?? { code: 'WORLD', name: '国际', flagUrl: null }
}

function movementForRank(rank: number): RankMovement {
  if (rank % 5 === 0) return { direction: 'flat', places: 0 }
  if (rank % 2 === 0) return { direction: 'up', places: (rank % 4) + 1 }
  return { direction: 'down', places: (rank % 3) + 1 }
}

function createEntry(input: {
  id: string
  tour: TourKey
  name: string
  nameZh?: string | null
  shortName: string
  countryCode: string
  rank: number | null
  points: number | null
  movement?: RankMovement
  avatarUrl?: string | null
  aliases?: string[]
}): PlayerDirectoryEntry {
  const playerCountry = country(input.countryCode)
  return {
    id: input.id,
    tour: input.tour,
    name: input.name,
    nameZh: input.nameZh ?? null,
    shortName: input.shortName,
    countryCode: playerCountry.code,
    countryName: playerCountry.name,
    flagUrl: playerCountry.flagUrl,
    rank: input.rank,
    points: input.points,
    movement: input.movement ?? { direction: 'flat', places: 0 },
    avatarUrl: input.avatarUrl ?? null,
    aliases: input.aliases ?? [],
  }
}

const atpFirstNames = [
  ['Adrian', '阿德里安'],
  ['Felix', '费利克斯'],
  ['Matteo', '马泰奥'],
  ['Tommy', '汤米'],
  ['Sebastian', '塞巴斯蒂安'],
  ['Arthur', '阿图尔'],
  ['Alexei', '阿列克谢'],
  ['Daniel', '丹尼尔'],
  ['Nicolas', '尼古拉斯'],
  ['Francisco', '弗朗西斯科'],
  ['Luca', '卢卡'],
  ['Gabriel', '加布里埃尔'],
  ['Jordan', '乔丹'],
  ['Maxime', '马克西姆'],
  ['Pedro', '佩德罗'],
  ['Hugo', '雨果'],
  ['Roman', '罗曼'],
  ['Alejandro', '亚历杭德罗'],
  ['Tomas', '托马斯'],
  ['David', '大卫'],
] as const

const wtaFirstNames = [
  ['Anna', '安娜'],
  ['Sofia', '索菲亚'],
  ['Marta', '玛尔塔'],
  ['Clara', '克拉拉'],
  ['Elena', '埃琳娜'],
  ['Maya', '玛雅'],
  ['Daria', '达里娅'],
  ['Linda', '琳达'],
  ['Camila', '卡米拉'],
  ['Eva', '伊娃'],
  ['Lucia', '露西亚'],
  ['Sara', '萨拉'],
  ['Nina', '妮娜'],
  ['Lea', '莱娅'],
  ['Maria', '玛丽亚'],
  ['Julia', '尤利娅'],
  ['Olivia', '奥利维娅'],
  ['Emilia', '艾米莉亚'],
  ['Laura', '劳拉'],
  ['Victoria', '维多利亚'],
] as const

const lastNames = [
  ['Martin', '马丁'],
  ['Garcia', '加西亚'],
  ['Novak', '诺瓦克'],
  ['Rossi', '罗西'],
  ['Meyer', '迈耶'],
  ['Costa', '科斯塔'],
  ['Petrov', '彼得罗夫'],
  ['Wilson', '威尔逊'],
  ['Tanaka', '田中'],
  ['Moreau', '莫罗'],
] as const

const countryRotation = ['FRA', 'ESP', 'ITA', 'USA', 'DEU', 'AUS', 'CAN', 'ARG', 'CHN', 'JPN', 'GBR', 'CZE', 'POL', 'NLD']

function generatedRanking(tour: TourKey, rank: number): PlayerDirectoryEntry {
  const firstNames = tour === 'ATP' ? atpFirstNames : wtaFirstNames
  const [firstName, firstNameZh] = firstNames[(rank - 1) % firstNames.length]
  const [lastName, lastNameZh] = lastNames[Math.floor((rank - 1) / firstNames.length) % lastNames.length]
  const name = `${firstName} ${lastName}`
  const countryCode = countryRotation[(rank + (tour === 'WTA' ? 5 : 0)) % countryRotation.length]
  return createEntry({
    id: `plr_${tour.toLowerCase()}_preview_${String(rank).padStart(3, '0')}`,
    tour,
    name,
    nameZh: `${lastNameZh}${firstNameZh}`,
    shortName: `${firstName.slice(0, 1)}. ${lastName}`,
    countryCode,
    rank,
    points: Math.max(118, Math.round(11_650 / Math.sqrt(rank) + (200 - rank) * 4.5)),
    movement: movementForRank(rank),
    aliases: [name, `${firstName.slice(0, 1)} ${lastName}`, `${lastNameZh}${firstNameZh}`],
  })
}

const atpSeeds: Record<number, PlayerDirectoryEntry> = {
  1: createEntry({ id: 'plr_atp_jannik_sinner', tour: 'ATP', name: 'Jannik Sinner', nameZh: '扬尼克·辛纳', shortName: 'J. Sinner', countryCode: 'ITA', rank: 1, points: 11780, aliases: ['Sinner', '辛纳'] }),
  2: createEntry({ id: 'plr_atp_carlos_alcaraz', tour: 'ATP', name: 'Carlos Alcaraz', nameZh: '卡洛斯·阿尔卡拉斯', shortName: 'C. Alcaraz', countryCode: 'ESP', rank: 2, points: 8580, movement: { direction: 'up', places: 1 }, aliases: ['Alcaraz', '阿尔卡拉斯'] }),
  3: createEntry({ id: 'plr_atp_alexander_zverev', tour: 'ATP', name: 'Alexander Zverev', nameZh: '亚历山大·兹维列夫', shortName: 'A. Zverev', countryCode: 'DEU', rank: 3, points: 7635, movement: { direction: 'down', places: 1 }, aliases: ['Zverev', '兹维列夫'] }),
  4: createEntry({ id: 'plr_atp_novak_djokovic', tour: 'ATP', name: 'Novak Djokovic', nameZh: '诺瓦克·德约科维奇', shortName: 'N. Djokovic', countryCode: 'SRB', rank: 4, points: 6500, aliases: ['Djokovic', '德约科维奇'] }),
  5: createEntry({ id: 'plr_atp_ben_shelton', tour: 'ATP', name: 'Ben Shelton', nameZh: '本·谢尔顿', shortName: 'B. Shelton', countryCode: 'USA', rank: 5, points: 5200, movement: { direction: 'up', places: 2 }, avatarUrl: '/players/ben-shelton.png', aliases: ['Shelton', 'B Shelton', 'B. Shelton', '本谢尔顿', '谢尔顿'] }),
  6: createEntry({ id: 'plr_atp_taylor_fritz', tour: 'ATP', name: 'Taylor Fritz', nameZh: '泰勒·弗里茨', shortName: 'T. Fritz', countryCode: 'USA', rank: 6, points: 5035, movement: { direction: 'down', places: 1 }, aliases: ['Fritz', '弗里茨'] }),
  7: createEntry({ id: 'plr_atp_alex_de_minaur', tour: 'ATP', name: 'Alex de Minaur', nameZh: '亚历克斯·德米纳尔', shortName: 'A. de Minaur', countryCode: 'AUS', rank: 7, points: 4215, movement: { direction: 'up', places: 1 }, aliases: ['de Minaur', '德米纳尔'] }),
  8: createEntry({ id: 'plr_atp_lorenzo_musetti', tour: 'ATP', name: 'Lorenzo Musetti', nameZh: '洛伦佐·穆塞蒂', shortName: 'L. Musetti', countryCode: 'ITA', rank: 8, points: 3860, aliases: ['Musetti', '穆塞蒂'] }),
  9: createEntry({ id: 'plr_atp_jack_draper', tour: 'ATP', name: 'Jack Draper', nameZh: '杰克·德雷珀', shortName: 'J. Draper', countryCode: 'GBR', rank: 9, points: 3725, movement: { direction: 'up', places: 3 }, aliases: ['Draper', '德雷珀'] }),
  10: createEntry({ id: 'plr_atp_holger_rune', tour: 'ATP', name: 'Holger Rune', nameZh: '霍尔格·鲁内', shortName: 'H. Rune', countryCode: 'DNK', rank: 10, points: 3440, aliases: ['Rune', '鲁内'] }),
  40: createEntry({ id: 'plr_atp_zhizhen_zhang', tour: 'ATP', name: 'Zhizhen Zhang', nameZh: '张之臻', shortName: 'Z. Zhang', countryCode: 'CHN', rank: 40, points: 1160, movement: { direction: 'up', places: 4 }, aliases: ['Zhang Zhizhen', '张之臻', 'Z Zhang'] }),
  50: createEntry({ id: 'plr_atp_zizou_bergs', tour: 'ATP', name: 'Zizou Bergs', nameZh: '齐祖·贝尔赫斯', shortName: 'Z. Bergs', countryCode: 'BEL', rank: 50, points: 1025, movement: { direction: 'up', places: 2 }, aliases: ['Bergs', '贝尔赫斯'] }),
  55: createEntry({ id: 'plr_atp_juncheng_shang', tour: 'ATP', name: 'Juncheng Shang', nameZh: '商竣程', shortName: 'J. Shang', countryCode: 'CHN', rank: 55, points: 925, movement: { direction: 'down', places: 2 }, aliases: ['Shang Juncheng', '商竣程'] }),
  90: createEntry({ id: 'plr_atp_yibing_wu', tour: 'ATP', name: 'Yibing Wu', nameZh: '吴易昺', shortName: 'Y. Wu', countryCode: 'CHN', rank: 90, points: 675, movement: { direction: 'up', places: 5 }, aliases: ['Wu Yibing', '吴易昺'] }),
  200: createEntry({ id: 'plr_atp_eliot_spizzirri', tour: 'ATP', name: 'Eliot Spizzirri', nameZh: '埃利奥特·斯皮齐里', shortName: 'E. Spizzirri', countryCode: 'USA', rank: 200, points: 302, movement: { direction: 'down', places: 3 }, aliases: ['Spizzirri', '斯皮齐里'] }),
}

const wtaSeeds: Record<number, PlayerDirectoryEntry> = {
  1: createEntry({ id: 'plr_wta_aryna_sabalenka', tour: 'WTA', name: 'Aryna Sabalenka', nameZh: '阿丽娜·萨巴伦卡', shortName: 'A. Sabalenka', countryCode: 'BLR', rank: 1, points: 11105, aliases: ['Sabalenka', '萨巴伦卡'] }),
  2: createEntry({ id: 'plr_wta_iga_swiatek', tour: 'WTA', name: 'Iga Swiatek', nameZh: '伊加·斯瓦泰克', shortName: 'I. Swiatek', countryCode: 'POL', rank: 2, points: 9320, movement: { direction: 'up', places: 1 }, aliases: ['Swiatek', '斯瓦泰克'] }),
  3: createEntry({ id: 'plr_wta_coco_gauff', tour: 'WTA', name: 'Coco Gauff', nameZh: '科科·高芙', shortName: 'C. Gauff', countryCode: 'USA', rank: 3, points: 7298, movement: { direction: 'down', places: 1 }, aliases: ['Gauff', '高芙'] }),
  4: createEntry({ id: 'plr_wta_elena_rybakina', tour: 'WTA', name: 'Elena Rybakina', nameZh: '埃琳娜·莱巴金娜', shortName: 'E. Rybakina', countryCode: 'KAZ', rank: 4, points: 6480, aliases: ['Rybakina', '莱巴金娜'] }),
  5: createEntry({ id: 'plr_wta_qinwen_zheng', tour: 'WTA', name: 'Qinwen Zheng', nameZh: '郑钦文', shortName: 'Q. Zheng', countryCode: 'CHN', rank: 5, points: 5315, movement: { direction: 'up', places: 2 }, avatarUrl: '/players/qinwen-zheng.png', aliases: ['Zheng Qinwen', 'Q Zheng', 'Q. Zheng', '郑钦文', '钦文'] }),
  25: createEntry({ id: 'plr_wta_xinyu_wang', tour: 'WTA', name: 'Xinyu Wang', nameZh: '王欣瑜', shortName: 'X. Wang', countryCode: 'CHN', rank: 25, points: 1830, movement: { direction: 'up', places: 3 }, aliases: ['Wang Xinyu', '王欣瑜'] }),
  45: createEntry({ id: 'plr_wta_yue_yuan', tour: 'WTA', name: 'Yue Yuan', nameZh: '袁悦', shortName: 'Y. Yuan', countryCode: 'CHN', rank: 45, points: 1165, movement: { direction: 'down', places: 2 }, aliases: ['Yuan Yue', '袁悦'] }),
  50: createEntry({ id: 'plr_wta_xiyu_wang', tour: 'WTA', name: 'Xiyu Wang', nameZh: '王曦雨', shortName: 'X. Wang', countryCode: 'CHN', rank: 50, points: 1080, movement: { direction: 'up', places: 1 }, aliases: ['Wang Xiyu', '王曦雨'] }),
  200: createEntry({ id: 'plr_wta_emina_bektas', tour: 'WTA', name: 'Emina Bektas', nameZh: '埃米娜·贝克塔斯', shortName: 'E. Bektas', countryCode: 'USA', rank: 200, points: 286, movement: { direction: 'down', places: 4 }, aliases: ['Bektas', '贝克塔斯'] }),
}

function createRankings(tour: TourKey) {
  const seeds = tour === 'ATP' ? atpSeeds : wtaSeeds
  return Array.from({ length: 200 }, (_, index) => {
    const rank = index + 1
    return seeds[rank] ?? generatedRanking(tour, rank)
  })
}

export const PLAYER_RANKINGS: Record<TourKey, PlayerDirectoryEntry[]> = {
  ATP: createRankings('ATP'),
  WTA: createRankings('WTA'),
}

const extendedDirectory = [
  createEntry({ id: 'plr_atp_coleman_wong', tour: 'ATP', name: 'Coleman Wong', nameZh: '黄泽林', shortName: 'C. Wong', countryCode: 'HKG', rank: 201, points: 296, movement: { direction: 'up', places: 6 }, aliases: ['Wong Coleman', '黄泽林', 'Coleman'] }),
  createEntry({ id: 'plr_wta_maya_joint', tour: 'WTA', name: 'Maya Joint', nameZh: '玛雅·乔因特', shortName: 'M. Joint', countryCode: 'AUS', rank: 201, points: 278, movement: { direction: 'down', places: 2 }, aliases: ['Joint', '乔因特'] }),
  createEntry({ id: 'plr_atp_bryan_shelton', tour: 'ATP', name: 'Bryan Shelton', nameZh: '布莱恩·谢尔顿', shortName: 'B. Shelton', countryCode: 'USA', rank: null, points: null, aliases: ['Shelton', 'B Shelton', 'B. Shelton', '布莱恩谢尔顿', '谢尔顿'] }),
  createEntry({ id: 'plr_wta_mei_lin', tour: 'WTA', name: 'Mei Lin', nameZh: '林玫', shortName: 'M. Lin', countryCode: 'CHN', rank: null, points: null, aliases: ['Lin Mei', '林玫'] }),
]

export const PLAYER_DIRECTORY = [
  ...PLAYER_RANKINGS.ATP,
  ...PLAYER_RANKINGS.WTA,
  ...extendedDirectory,
]

function normalizeSearchValue(value: string) {
  return value
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLocaleLowerCase('en-US')
    .replace(/[.'’·_-]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
}

export function searchPlayerDirectory(
  players: PlayerDirectoryEntry[],
  filters: { query: string; tour: TourKey; countryCode: string },
) {
  const query = normalizeSearchValue(filters.query)
  if (!query) return []
  const compactQuery = query.replace(/\s/g, '')

  return players.filter((player) => {
    if (player.tour !== filters.tour) return false
    if (filters.countryCode !== 'ALL' && player.countryCode !== filters.countryCode) return false
    const values = [player.name, player.nameZh ?? '', player.shortName, ...player.aliases]
    return values.some((value) => {
      const normalized = normalizeSearchValue(value)
      return normalized.includes(query) || normalized.replace(/\s/g, '').includes(compactQuery)
    })
  })
}

function profileForEntry(entry: PlayerDirectoryEntry): PlayerProfilePreview {
  const profileDetails: Record<string, Pick<PlayerProfilePreview, 'birthDate' | 'age'>> = {
    plr_atp_ben_shelton: { birthDate: '2002-10-09', age: 23 },
    plr_wta_qinwen_zheng: { birthDate: '2002-10-08', age: 23 },
    plr_atp_bryan_shelton: { birthDate: null, age: null },
  }
  const details = profileDetails[entry.id] ?? { birthDate: null, age: null }
  return {
    ...entry,
    ...details,
    rankUpdatedAt: '2026-09-11 09:00 UTC',
  }
}

function seasonSummariesFor(profile: PlayerProfilePreview): PlayerSeasonSummaryPreview[] {
  const unavailable = profile.rank === null && profile.birthDate === null
  return [2026, 2025, 2024, 2023, 2022].map((season, index) => {
    if (unavailable) {
      return {
        season,
        matches: null,
        wins: null,
        losses: null,
        winRate: null,
        titles: null,
        hardWinRate: null,
        clayWinRate: null,
        grassWinRate: null,
      }
    }
    const tourAdjustment = profile.tour === 'WTA' ? 2 : 0
    const matches = 47 - index * 3 + tourAdjustment
    const wins = 35 - index * 3 + tourAdjustment
    const losses = matches - wins
    return {
      season,
      matches,
      wins,
      losses,
      winRate: Number(((wins / matches) * 100).toFixed(1)),
      titles: Math.max(0, 3 - index),
      hardWinRate: 78 - index * 2 + tourAdjustment,
      clayWinRate: 66 - index + tourAdjustment,
      grassWinRate: 72 - index * 2,
    }
  })
}

const atpOpponents = [
  ['Carlos Alcaraz', '卡洛斯·阿尔卡拉斯', 'ESP'],
  ['Taylor Fritz', '泰勒·弗里茨', 'USA'],
  ['Alex de Minaur', '亚历克斯·德米纳尔', 'AUS'],
  ['Lorenzo Musetti', '洛伦佐·穆塞蒂', 'ITA'],
  ['Holger Rune', '霍尔格·鲁内', 'DNK'],
  ['Casper Ruud', '卡斯珀·鲁德', 'NOR'],
] as const

const wtaOpponents = [
  ['Aryna Sabalenka', '阿丽娜·萨巴伦卡', 'BLR'],
  ['Iga Swiatek', '伊加·斯瓦泰克', 'POL'],
  ['Coco Gauff', '科科·高芙', 'USA'],
  ['Elena Rybakina', '埃琳娜·莱巴金娜', 'KAZ'],
  ['Jessica Pegula', '杰西卡·佩古拉', 'USA'],
  ['Karolina Muchova', '卡洛琳娜·穆霍娃', 'CZE'],
] as const

const tournamentSeeds = [
  ['US Open', '美国网球公开赛', '硬地'],
  ['Cincinnati Open', '辛辛那提公开赛', '硬地'],
  ['Canadian Open', '加拿大公开赛', '硬地'],
  ['Wimbledon', '温布尔登锦标赛', '草地'],
  ['Roland Garros', '法国网球公开赛', '红土'],
  ['Madrid Open', '马德里公开赛', '红土'],
] as const

const roundLabels = ['决赛', '半决赛', '四分之一决赛', '第四轮', '第三轮', '第二轮']

function resultsFor(profile: PlayerProfilePreview): PlayerResultPreview[] {
  const opponents = profile.tour === 'ATP' ? atpOpponents : wtaOpponents
  return [2026, 2025, 2024, 2023, 2022].flatMap((season) => {
    const count = season === 2026 ? 27 : 12
    return Array.from({ length: count }, (_, index) => {
      const [opponentName, opponentNameZh, opponentCountryCode] = opponents[index % opponents.length]
      const opponentCountry = country(opponentCountryCode)
      const [tournament, tournamentZh, surface] = tournamentSeeds[(index + season) % tournamentSeeds.length]
      const outcome: MatchOutcome = index % 3 === 2 ? 'loss' : 'win'
      let tier: CompetitionTier = profile.tour
      if (index % 11 === 10) tier = 'ITF'
      else if (index % 7 === 6) tier = 'Challenger'
      const month = Math.max(1, 9 - Math.floor(index / 3))
      const day = 27 - (index % 3) * 5
      return {
        id: `result_${profile.id}_${season}_${String(index + 1).padStart(2, '0')}`,
        matchId: `mtch_${profile.tour.toLowerCase()}_${season}_${String(index + 1).padStart(3, '0')}`,
        season,
        date: `${season}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`,
        tournament,
        tournamentZh,
        tier,
        surface,
        round: roundLabels[index % roundLabels.length],
        opponent: {
          name: opponentName,
          nameZh: opponentNameZh,
          countryCode: opponentCountry.code,
          countryName: opponentCountry.name,
          flagUrl: opponentCountry.flagUrl,
        },
        outcome,
        score: outcome === 'win' ? (index % 2 === 0 ? '6–4 6–3' : '4–6 7–5 6–2') : '6–7 4–6',
      }
    })
  })
}

function scenarioForPlayer(playerId: string): PlayerProfileScenario {
  const entry = PLAYER_DIRECTORY.find((player) => player.id === playerId) ?? PLAYER_RANKINGS.ATP[0]
  const profile = profileForEntry(entry)
  const isBen = profile.id === 'plr_atp_ben_shelton'
  const isQinwen = profile.id === 'plr_wta_qinwen_zheng'
  const isMissing = profile.id === 'plr_atp_bryan_shelton' || (profile.birthDate === null && profile.avatarUrl === null)
  return {
    profile,
    seasonSummaries: seasonSummariesFor(profile),
    results: resultsFor(profile),
    defaultStatus: isBen ? 'live' : isQinwen ? 'next' : 'none',
    defaultHistoryState: isMissing ? 'unavailable' : 'ready',
  }
}

export function currentStatusFor(
  profile: PlayerProfilePreview,
  status: ProfileStatusKey,
): PlayerCurrentStatusPreview {
  if (status === 'none') {
    return { kind: 'none', message: '当前没有可用的正在进行或即将开始的单打比赛。' }
  }

  const opponentSeed = profile.tour === 'ATP' ? atpOpponents[2] : wtaOpponents[2]
  const opponentCountry = country(opponentSeed[2])
  const opponent = {
    name: opponentSeed[0],
    nameZh: opponentSeed[1],
    countryCode: opponentCountry.code,
    countryName: opponentCountry.name,
    flagUrl: opponentCountry.flagUrl,
  }

  if (status === 'live') {
    return {
      kind: 'live',
      matchId: `mtch_live_${profile.id}`,
      event: profile.tour === 'ATP' ? 'Cincinnati Open' : 'Wuhan Open',
      round: '四分之一决赛',
      opponent,
      score: '6–4 3–2 · 40–30',
      detail: '第二盘 · 当前由本球员发球',
      freshness: '刚刚更新',
    }
  }

  return {
    kind: 'next',
    matchId: `mtch_next_${profile.id}`,
    event: profile.tour === 'ATP' ? 'US Open' : 'China Open',
    round: '第四轮',
    opponent,
    startLabel: '今天 21:30',
    countdown: '约 3 小时后',
  }
}

export function getPlayerProfileBundle(playerId: string): PlayerProfileBundle {
  const scenarioIds = [playerId, 'plr_atp_ben_shelton', 'plr_wta_qinwen_zheng', 'plr_atp_bryan_shelton']
  const uniqueIds = Array.from(new Set(scenarioIds))
  return {
    currentPlayerId: scenarioForPlayer(playerId).profile.id,
    scenarios: uniqueIds.map(scenarioForPlayer),
  }
}
