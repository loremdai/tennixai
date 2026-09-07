export type MatchPlayer = {
  name: string
  shortName: string
  country: string
  flagUrl: string
  rank?: number
  sets: string[]
  pointScore: string
  serving?: boolean
}

export type LiveMatch = {
  id: string
  href: string
  tournament: string
  round: string
  currentSet: string
  elapsed: string
  players: [MatchPlayer, MatchPlayer]
}

export const featuredMatch: LiveMatch = {
  id: 'sinner-alcaraz',
  href: '/match',
  tournament: 'ATP 年终总决赛',
  round: '半决赛',
  currentSet: '第三盘',
  elapsed: '2 小时 12 分',
  players: [
    {
      name: 'Jannik Sinner',
      shortName: 'Sinner',
      country: '意大利',
      flagUrl: 'https://flagcdn.com/w40/it.png',
      rank: 1,
      sets: ['6', '4'],
      pointScore: '30',
      serving: true,
    },
    {
      name: 'Carlos Alcaraz',
      shortName: 'Alcaraz',
      country: '西班牙',
      flagUrl: 'https://flagcdn.com/w40/es.png',
      rank: 2,
      sets: ['4', '5'],
      pointScore: '15',
    },
  ],
}

export const liveMatches: LiveMatch[] = [
  featuredMatch,
  {
    id: 'swiatek-sabalenka',
    href: '/match',
    tournament: 'WTA 年终总决赛',
    round: '半决赛',
    currentSet: '第二盘',
    elapsed: '1 小时 08 分',
    players: [
      {
        name: 'Iga Swiatek',
        shortName: 'Swiatek',
        country: '波兰',
        flagUrl: 'https://flagcdn.com/w40/pl.png',
        sets: ['6', '2'],
        pointScore: '40',
      },
      {
        name: 'Aryna Sabalenka',
        shortName: 'Sabalenka',
        country: '白俄罗斯',
        flagUrl: 'https://flagcdn.com/w40/by.png',
        sets: ['3', '3'],
        pointScore: '30',
        serving: true,
      },
    ],
  },
  {
    id: 'zverev-rune',
    href: '/match',
    tournament: 'ATP 巴塞尔站',
    round: '八强',
    currentSet: '第一盘',
    elapsed: '38 分钟',
    players: [
      {
        name: 'Alexander Zverev',
        shortName: 'Zverev',
        country: '德国',
        flagUrl: 'https://flagcdn.com/w40/de.png',
        sets: ['4'],
        pointScore: '15',
        serving: true,
      },
      {
        name: 'Holger Rune',
        shortName: 'Rune',
        country: '丹麦',
        flagUrl: 'https://flagcdn.com/w40/dk.png',
        sets: ['3'],
        pointScore: '15',
      },
    ],
  },
]

export const upcomingMatches = [
  {
    id: 'medvedev-fritz',
    href: '/match',
    tournament: 'ATP 年终总决赛',
    round: '小组赛',
    time: '20:30',
    surface: '室内硬地',
    players: [
      { name: 'Daniil Medvedev', country: '俄罗斯', flagUrl: 'https://flagcdn.com/w40/ru.png' },
      { name: 'Taylor Fritz', country: '美国', flagUrl: 'https://flagcdn.com/w40/us.png' },
    ],
  },
  {
    id: 'rybakina-gauff',
    href: '/match',
    tournament: 'WTA 年终总决赛',
    round: '小组赛',
    time: '21:00',
    surface: '硬地',
    players: [
      { name: 'Elena Rybakina', country: '哈萨克斯坦', flagUrl: 'https://flagcdn.com/w40/kz.png' },
      { name: 'Coco Gauff', country: '美国', flagUrl: 'https://flagcdn.com/w40/us.png' },
    ],
  },
  {
    id: 'tsitsipas-ruud',
    href: '/match',
    tournament: 'ATP 年终总决赛',
    round: '小组赛',
    time: '21:30',
    surface: '室内硬地',
    players: [
      { name: 'Stefanos Tsitsipas', country: '希腊', flagUrl: 'https://flagcdn.com/w40/gr.png' },
      { name: 'Casper Ruud', country: '挪威', flagUrl: 'https://flagcdn.com/w40/no.png' },
    ],
  },
  {
    id: 'rublev-hurkacz',
    href: '/match',
    tournament: 'ATP 巴塞尔站',
    round: '八强',
    time: '22:00',
    surface: '硬地',
    players: [
      { name: 'Andrey Rublev', country: '俄罗斯', flagUrl: 'https://flagcdn.com/w40/ru.png' },
      { name: 'Hubert Hurkacz', country: '波兰', flagUrl: 'https://flagcdn.com/w40/pl.png' },
    ],
  },
] as const

export const followedPlayers = [
  {
    id: 'sinner',
    name: 'Jannik Sinner',
    rank: 1,
    country: '意大利',
    flagUrl: 'https://flagcdn.com/w40/it.png',
    portrait: '/images/player-sinner.png',
    status: '今日 20:30',
    detail: '对阵 Alcaraz',
    live: false,
  },
  {
    id: 'alcaraz',
    name: 'Carlos Alcaraz',
    rank: 2,
    country: '西班牙',
    flagUrl: 'https://flagcdn.com/w40/es.png',
    portrait: '/images/player-alcaraz.png',
    status: '正在比赛',
    detail: '第三盘 5–4',
    live: true,
  },
  {
    id: 'djokovic',
    name: 'Novak Djokovic',
    rank: 4,
    country: '塞尔维亚',
    flagUrl: 'https://flagcdn.com/w40/rs.png',
    portrait: '/images/player-djokovic.png',
    status: '明日 19:00',
    detail: '对阵 Ruud',
    live: false,
  },
  {
    id: 'sabalenka',
    name: 'Aryna Sabalenka',
    rank: 1,
    country: '白俄罗斯',
    flagUrl: 'https://flagcdn.com/w40/by.png',
    portrait: '/images/player-sabalenka.png',
    status: '正在比赛',
    detail: '第二盘 3–2',
    live: true,
  },
] as const

export const recentResults = [
  {
    id: 'sinner-zverev',
    tournament: 'ATP 年终总决赛',
    round: '半决赛',
    winner: { name: 'Sinner', flagUrl: 'https://flagcdn.com/w40/it.png', country: '意大利' },
    loser: { name: 'Zverev', flagUrl: 'https://flagcdn.com/w40/de.png', country: '德国' },
    score: '6–4  7–6',
  },
  {
    id: 'gauff-pegula',
    tournament: 'WTA 年终总决赛',
    round: '小组赛',
    winner: { name: 'Gauff', flagUrl: 'https://flagcdn.com/w40/us.png', country: '美国' },
    loser: { name: 'Pegula', flagUrl: 'https://flagcdn.com/w40/us.png', country: '美国' },
    score: '7–5  6–3',
  },
  {
    id: 'ruud-rublev',
    tournament: 'ATP 巴塞尔站',
    round: '八强',
    winner: { name: 'Ruud', flagUrl: 'https://flagcdn.com/w40/no.png', country: '挪威' },
    loser: { name: 'Rublev', flagUrl: 'https://flagcdn.com/w40/ru.png', country: '俄罗斯' },
    score: '6–2  4–6  6–3',
  },
] as const

export type HomeMatchStatus = 'upcoming' | 'live' | 'finished'

export type HomeMatchResult = {
  id: string
  href: string
  actionLabel?: string
  status: HomeMatchStatus
  tournament: string
  round: string
  time: string
  surface: string
  location: string
  players: [string, string]
  score?: {
    currentSet: string
    note: string
    rows: [
      { player: string; sets: string[]; points: string; serving?: boolean },
      { player: string; sets: string[]; points: string; serving?: boolean },
    ]
  }
}

export type HomeAnswer = {
  label: string
  question: string
  title: string
  summary: string
  matches: HomeMatchResult[]
  source: string
}

export const homeExampleQueries = [
  'Sinner 今晚几点比赛？',
  'Alcaraz 今天比赛吗？',
  '现在比分是多少？',
  'Djokovic 下一场对阵谁？',
  '显示今晚的比赛',
] as const

const sinnerUpcomingMatch: HomeMatchResult = {
  id: 'sinner-alcaraz-upcoming',
  href: '/match?status=upcoming',
  status: 'upcoming',
  tournament: 'ATP Finals',
  round: '半决赛',
  time: '今晚 · 20:30',
  surface: '室内硬地',
  location: '都灵，意大利',
  players: ['Jannik Sinner', 'Carlos Alcaraz'],
}

const sinnerLiveMatch: HomeMatchResult = {
  ...sinnerUpcomingMatch,
  id: 'sinner-alcaraz-live',
  href: '/match?status=live',
  status: 'live',
  time: '进行中 · 2 小时 12 分',
  score: {
    currentSet: '第三盘',
    note: 'Sinner 发球',
    rows: [
      { player: 'Sinner', sets: ['6', '4', '4'], points: '30', serving: true },
      { player: 'Alcaraz', sets: ['4', '6', '5'], points: '15' },
    ],
  },
}

const djokovicMatch: HomeMatchResult = {
  id: 'djokovic-ruud-upcoming',
  href: '#players',
  actionLabel: '查看球员',
  status: 'upcoming',
  tournament: 'ATP Finals',
  round: '小组赛',
  time: '明晚 · 19:00',
  surface: '室内硬地',
  location: '都灵，意大利',
  players: ['Novak Djokovic', 'Casper Ruud'],
}

const tonightMatches: HomeMatchResult[] = [
  sinnerUpcomingMatch,
  {
    id: 'medvedev-fritz-tonight',
    href: '#upcoming',
    actionLabel: '查看赛程',
    status: 'upcoming',
    tournament: 'ATP Finals',
    round: '小组赛',
    time: '今晚 · 21:00',
    surface: '室内硬地',
    location: '都灵，意大利',
    players: ['Daniil Medvedev', 'Taylor Fritz'],
  },
  {
    id: 'rybakina-gauff-tonight',
    href: '#upcoming',
    actionLabel: '查看赛程',
    status: 'upcoming',
    tournament: 'WTA Finals',
    round: '小组赛',
    time: '今晚 · 22:30',
    surface: '硬地',
    location: '利雅得，沙特阿拉伯',
    players: ['Elena Rybakina', 'Coco Gauff'],
  },
]

export function answerHomeQuestion(question: string): HomeAnswer {
  const normalized = question.trim().toLowerCase()

  if (
    normalized.includes('live score') ||
    normalized.includes('实时比分') ||
    normalized.includes('现在比分') ||
    normalized.includes('比分是多少')
  ) {
    return {
      label: '实时比赛数据',
      question,
      title: 'Sinner 与 Alcaraz 正在进行第三盘',
      summary: 'Alcaraz 以 5–4 领先当前盘，Sinner 正在发球，当前局分为 30–15。',
      matches: [sinnerLiveMatch],
      source: '官方逐分数据 · 延迟约 2.4 秒',
    }
  }

  if (normalized.includes('djokovic') || normalized.includes('德约科维奇')) {
    return {
      label: '下一场比赛',
      question,
      title: 'Djokovic 下一场对阵 Casper Ruud',
      summary: '这场 ATP Finals 小组赛安排在明晚 19:00，于都灵室内硬地进行。',
      matches: [djokovicMatch],
      source: 'ATP 官方赛程 · 已核验',
    }
  }

  if (
    normalized.includes('显示今晚') ||
    normalized.includes('今晚的比赛') ||
    normalized.includes("tonight's matches") ||
    normalized.includes('show me tonight')
  ) {
    return {
      label: '今晚赛程',
      question,
      title: '今晚有 3 场重点比赛',
      summary: '已按你的本地时间排序，最早一场于 20:30 开始。',
      matches: tonightMatches,
      source: 'ATP 与 WTA 官方赛程 · 本地时间',
    }
  }

  if (normalized.includes('alcaraz') || normalized.includes('阿尔卡拉斯')) {
    return {
      label: '今日赛程',
      question,
      title: '是的，Alcaraz 今晚有比赛',
      summary: 'Carlos Alcaraz 将在今晚 20:30 对阵 Jannik Sinner。',
      matches: [sinnerUpcomingMatch],
      source: 'ATP 官方赛程 · 已核验',
    }
  }

  if (normalized.includes('价值') || normalized.includes('市场') || normalized.includes('优势')) {
    return {
      label: '能力预告',
      question,
      title: '市场智能将在 P3 开放',
      summary: '当前 P1 原型优先帮助你发现比赛、确认赛程，并进入单场比赛上下文。',
      matches: [sinnerUpcomingMatch],
      source: 'Tennix 产品路线图',
    }
  }

  return {
    label: '赛程已确认',
    question,
    title: 'Sinner 今晚 20:30 出场',
    summary: 'Jannik Sinner 将在 ATP Finals 半决赛中对阵 Carlos Alcaraz。',
    matches: [sinnerUpcomingMatch],
    source: 'ATP 官方赛程 · 已核验 4 个数据源',
  }
}
