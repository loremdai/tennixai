import Link from 'next/link'
import { ChevronRight, SearchX } from 'lucide-react'

import { PlayerCountry } from '@/components/player-country'
import { PlayerAvatar } from '@/components/player-avatar'
import { PlayerName } from '@/components/player-name'
import type { PlayerDirectoryEntry } from '@/components/players/player-preview-data'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardAction,
  CardContent,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'

export function PlayerSearchResults({
  query,
  countryName,
  players,
  onClear,
}: {
  query: string
  countryName: string | null
  players: PlayerDirectoryEntry[]
  onClear: () => void
}) {
  return (
    <Card aria-labelledby="player-search-results-title">
      <CardHeader className="border-b">
        <div>
          <CardTitle>
            <h2 id="player-search-results-title">全目录搜索结果</h2>
          </CardTitle>
          <p className="mt-1 text-sm leading-relaxed text-muted-foreground">
            “{query}”{countryName ? ` · ${countryName}` : ''}
          </p>
        </div>
        <CardAction>
          <Badge variant="secondary">{players.length} 位球员</Badge>
        </CardAction>
      </CardHeader>

      <CardContent className="-mx-(--card-spacing)">
        {players.length ? (
          <ul className="flex flex-col" aria-label="球员搜索结果列表">
            {players.map((player) => (
              <li key={player.id}>
                <Link
                  href={`/players/${player.id}`}
                  aria-label={`打开 ${player.name}${player.nameZh ? `，${player.nameZh}` : ''} 的球员资料`}
                  className="group flex items-center gap-3 border-b px-4 py-4 transition-colors last:border-b-0 hover:bg-muted/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring md:gap-4"
                >
                  <PlayerAvatar name={player.name} imageUrl={player.avatarUrl} className="size-12" />
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <PlayerName
                        name={player.name}
                        localizedName={player.nameZh}
                        className="font-medium text-foreground"
                      />
                      {player.tour ? <Badge variant="outline">{player.tour}</Badge> : null}
                    </div>
                    <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
                      <span className="inline-flex items-center gap-1.5">
                        <PlayerCountry player={player} />
                        {player.countryName}
                      </span>
                    </div>
                  </div>
                  <div className="flex shrink-0 items-center gap-3">
                    <div className="text-right">
                      <p className="font-mono text-sm font-semibold tabular-nums">
                        {player.rank ? `#${player.rank}` : '暂无当前排名'}
                      </p>
                      <p className="mt-0.5 hidden text-xs text-muted-foreground sm:block">
                        {player.points ? `${player.points.toLocaleString('en-US')} 分` : '积分暂无'}
                      </p>
                    </div>
                    <ChevronRight aria-hidden="true" className="size-4 text-muted-foreground transition-transform group-hover:translate-x-0.5 group-hover:text-foreground" />
                  </div>
                </Link>
              </li>
            ))}
          </ul>
        ) : (
          <div className="flex min-h-72 flex-col items-center justify-center gap-3 px-4 text-center">
            <span className="flex size-12 items-center justify-center rounded-full bg-muted text-muted-foreground">
              <SearchX aria-hidden="true" className="size-5" />
            </span>
            <div className="flex max-w-md flex-col gap-1">
              <p className="font-medium">未找到匹配球员</p>
              <p className="text-sm leading-relaxed text-muted-foreground">
                请检查拼写，尝试完整英文名、中文名、姓氏或“首字母 + 姓氏”。
              </p>
            </div>
            <Button type="button" variant="outline" onClick={onClear}>返回排名</Button>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
