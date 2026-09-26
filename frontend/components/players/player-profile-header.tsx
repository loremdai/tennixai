import { ArrowDown, ArrowUp, CalendarDays, Minus } from 'lucide-react'

import { PlayerCountry } from '@/components/player-country'
import { PlayerAvatar } from '@/components/player-avatar'
import type { PlayerProfilePreview, RankMovement } from '@/components/players/player-preview-data'
import { Badge } from '@/components/ui/badge'
import { formatAsOf } from '@/lib/view-models'
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'

function formatBirthDate(value: string) {
  const [year, month, day] = value.split('-')
  return `${year}年${Number(month)}月${Number(day)}日`
}

function MovementValue({ movement, unavailable }: { movement: RankMovement; unavailable: boolean }) {
  if (unavailable || movement.direction === 'unknown') {
    return <span className="text-sm font-medium text-muted-foreground">暂无变动</span>
  }
  if (movement.direction === 'flat') {
    return <span className="inline-flex items-center gap-1.5 font-mono font-semibold"><Minus aria-hidden="true" className="size-4" />持平</span>
  }
  const up = movement.direction === 'up'
  return (
    <span className={up ? 'inline-flex items-center gap-1.5 font-mono font-semibold text-live' : 'inline-flex items-center gap-1.5 font-mono font-semibold text-muted-foreground'}>
      {up ? <ArrowUp aria-hidden="true" className="size-4" /> : <ArrowDown aria-hidden="true" className="size-4" />}
      {movement.places !== null ? `${movement.places} 位` : up ? '上升' : '下降'}
    </span>
  )
}

export function PlayerProfileHeader({ profile }: { profile: PlayerProfilePreview }) {
  const rankUpdatedAt = formatAsOf(profile.rankUpdatedAt)

  return (
    <Card aria-labelledby="player-profile-name" className="[--card-spacing:--spacing(6)]">
      <CardHeader className="border-b">
        <div className="flex flex-wrap items-center gap-2">
          {profile.tour ? <Badge>{profile.tour}</Badge> : null}
          <Badge variant="outline">单打</Badge>
        </div>
        <CardTitle className="sr-only">球员资料</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-6">
        <div className="flex flex-col gap-5 sm:flex-row sm:items-center">
          <PlayerAvatar name={profile.name} imageUrl={profile.avatarUrl} className="!size-20 md:!size-24" />
          <div className="min-w-0 flex-1">
            <h1 id="player-profile-name" className="text-balance text-3xl font-semibold tracking-tight md:text-4xl">{profile.name}</h1>
            {profile.nameZh ? <p className="mt-1 text-lg text-muted-foreground">{profile.nameZh}</p> : null}
            <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-2 text-sm text-muted-foreground">
              <span className="inline-flex items-center gap-2 text-foreground">
                <PlayerCountry player={profile} />
                {profile.countryName}
                <span className="font-mono text-xs text-muted-foreground">{profile.countryCode}</span>
              </span>
              <span className="inline-flex items-center gap-2">
                <CalendarDays aria-hidden="true" className="size-4" />
                {profile.birthDate && profile.age !== null
                  ? `${formatBirthDate(profile.birthDate)} · ${profile.age} 岁`
                  : '出生日期与年龄暂无'}
              </span>
            </div>
          </div>
        </div>

        <div className="grid gap-3 sm:grid-cols-3">
          <div className="rounded-xl bg-muted/55 p-4">
            <p className="text-xs text-muted-foreground">当前世界排名</p>
            <p className="mt-2 font-mono text-2xl font-semibold tabular-nums">{profile.rank ? `#${profile.rank}` : '暂无当前排名'}</p>
          </div>
          <div className="rounded-xl bg-muted/55 p-4">
            <p className="text-xs text-muted-foreground">排名积分</p>
            <p className="mt-2 font-mono text-2xl font-semibold tabular-nums">{profile.points?.toLocaleString('en-US') ?? '暂无'}</p>
          </div>
          <div className="rounded-xl bg-muted/55 p-4">
            <p className="text-xs text-muted-foreground">排名变化</p>
            <div className="mt-2 min-h-8"><MovementValue movement={profile.movement} unavailable={profile.rank === null} /></div>
          </div>
        </div>

        <p className="text-xs text-muted-foreground">排名更新于：{rankUpdatedAt ? `${rankUpdatedAt}（北京时间）` : '暂无'}</p>
      </CardContent>
    </Card>
  )
}
