import Link from 'next/link'
import { ArrowDown, ArrowUp, ChevronLeft, ChevronRight, Minus } from 'lucide-react'

import { PlayerCountry } from '@/components/player-country'
import type {
  PlayerDirectoryEntry,
  RankMovement,
  TourKey,
} from '@/components/players/player-preview-data'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardAction,
  CardContent,
  CardFooter,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'

function Movement({ movement }: { movement: RankMovement }) {
  if (movement.direction === 'flat') {
    return (
      <span className="inline-flex items-center gap-1 text-muted-foreground" aria-label="排名持平">
        <Minus aria-hidden="true" className="size-3.5" />
      </span>
    )
  }
  const up = movement.direction === 'up'
  return (
    <span
      className={up ? 'inline-flex items-center gap-1 text-live' : 'inline-flex items-center gap-1 text-muted-foreground'}
      aria-label={`排名${up ? '上升' : '下降'} ${movement.places} 位`}
    >
      {up ? <ArrowUp aria-hidden="true" className="size-3.5" /> : <ArrowDown aria-hidden="true" className="size-3.5" />}
      <span className="font-mono text-xs tabular-nums">{movement.places}</span>
    </span>
  )
}

export function RankingsTable({
  tour,
  players,
  page,
  pageSize,
  onPageChange,
}: {
  tour: TourKey
  players: PlayerDirectoryEntry[]
  page: number
  pageSize: number
  onPageChange: (page: number) => void
}) {
  const totalPages = Math.max(1, Math.ceil(players.length / pageSize))
  const currentPage = Math.min(page, totalPages)
  const start = (currentPage - 1) * pageSize
  const visiblePlayers = players.slice(start, start + pageSize)
  const pageNumbers = Array.from({ length: totalPages }, (_, index) => index + 1)

  return (
    <Card aria-labelledby="rankings-title">
      <CardHeader className="border-b">
        <div>
          <CardTitle>
            <h2 id="rankings-title">{tour} 单打世界排名</h2>
          </CardTitle>
          <p className="mt-1 text-sm leading-relaxed text-muted-foreground">
            官方前 200 · 每页 50 位 · 排名与积分为确定性预览数据
          </p>
        </div>
        <CardAction>
          <Badge variant="outline">Top 200</Badge>
        </CardAction>
      </CardHeader>

      <CardContent className="-mx-(--card-spacing)">
        {visiblePlayers.length ? (
          <div role="region" aria-label={`${tour} 世界排名列表`}>
            <div className="hidden grid-cols-[5rem_minmax(0,1.6fr)_minmax(8rem,1fr)_8rem_2rem] items-center gap-4 border-b bg-muted/45 px-4 py-2.5 text-xs font-medium text-muted-foreground md:grid">
              <span>排名 / 变动</span>
              <span>球员</span>
              <span>国家 / 地区</span>
              <span className="text-right">积分</span>
              <span className="sr-only">查看</span>
            </div>
            <ol start={start + 1} className="flex flex-col">
              {visiblePlayers.map((player) => (
                <li key={player.id}>
                  <Link
                    href={`/players/${player.id}`}
                    aria-label={`查看 ${player.name}${player.nameZh ? `，${player.nameZh}` : ''} 的球员资料`}
                    className="group flex flex-col gap-3 border-b px-4 py-4 transition-colors last:border-b-0 hover:bg-muted/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring md:grid md:grid-cols-[5rem_minmax(0,1.6fr)_minmax(8rem,1fr)_8rem_2rem] md:items-center md:gap-4 md:py-3"
                  >
                    <div className="flex items-center justify-between gap-4 md:justify-start">
                      <span className="font-mono text-lg font-semibold tabular-nums">{player.rank}</span>
                      <Movement movement={player.movement} />
                    </div>
                    <div className="min-w-0">
                      <p className="truncate font-medium text-foreground">{player.name}</p>
                      {player.nameZh ? <p className="mt-0.5 truncate text-xs text-muted-foreground">{player.nameZh}</p> : null}
                    </div>
                    <div className="flex items-center gap-2 text-sm">
                      <PlayerCountry player={player} />
                      <span>{player.countryName}</span>
                      <span className="font-mono text-xs text-muted-foreground">{player.countryCode}</span>
                    </div>
                    <div className="flex items-baseline justify-between gap-3 md:block md:text-right">
                      <span className="text-xs text-muted-foreground md:hidden">积分</span>
                      <span className="font-mono font-semibold tabular-nums">{player.points?.toLocaleString('en-US')}</span>
                    </div>
                    <ChevronRight aria-hidden="true" className="hidden size-4 text-muted-foreground transition-transform group-hover:translate-x-0.5 group-hover:text-foreground md:block" />
                  </Link>
                </li>
              ))}
            </ol>
          </div>
        ) : (
          <div className="flex min-h-56 flex-col items-center justify-center gap-2 px-4 text-center">
            <p className="font-medium">当前筛选没有排名球员</p>
            <p className="max-w-md text-sm leading-relaxed text-muted-foreground">更换国家/地区筛选后再试。</p>
          </div>
        )}
      </CardContent>

      <CardFooter className="flex-col gap-3 bg-muted/35 md:flex-row md:justify-between">
        <p className="font-mono text-xs text-muted-foreground" aria-live="polite">
          {players.length ? `${start + 1}–${Math.min(start + pageSize, players.length)} / 共 ${players.length} 位` : '共 0 位'}
        </p>
        <nav className="flex flex-wrap items-center justify-center gap-1" aria-label="排名分页">
          <Button
            type="button"
            variant="ghost"
            size="sm"
            disabled={currentPage === 1}
            onClick={() => onPageChange(currentPage - 1)}
          >
            <ChevronLeft data-icon="inline-start" aria-hidden="true" />
            上一页
          </Button>
          {pageNumbers.map((pageNumber) => (
            <Button
              key={pageNumber}
              type="button"
              variant={pageNumber === currentPage ? 'default' : 'ghost'}
              size="icon-sm"
              aria-label={`第 ${pageNumber} 页`}
              aria-current={pageNumber === currentPage ? 'page' : undefined}
              onClick={() => onPageChange(pageNumber)}
            >
              {pageNumber}
            </Button>
          ))}
          <Button
            type="button"
            variant="ghost"
            size="sm"
            disabled={currentPage === totalPages}
            onClick={() => onPageChange(currentPage + 1)}
          >
            下一页
            <ChevronRight data-icon="inline-end" aria-hidden="true" />
          </Button>
        </nav>
      </CardFooter>
    </Card>
  )
}
