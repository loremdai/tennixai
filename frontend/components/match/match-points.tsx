'use client'

import { useEffect, useMemo, useRef, useState } from 'react'
import { ChevronDown } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import type { PlayerDto, PointEventDto } from '@/lib/api/types'
import { cn } from '@/lib/utils'

type GameGroup = {
  setNumber: number
  gameNumber: number
  points: PointEventDto[]
}

const NEAR_BOTTOM_PX = 80

function shortName(name: string): string {
  const parts = name.trim().split(/\s+/)
  return parts[parts.length - 1] || name
}

function pointScore(point: PointEventDto): string {
  return `${point.score_after.points[0] ?? '-'} - ${point.score_after.points[1] ?? '-'}`
}

function keyPointBadges(point: PointEventDto): string[] {
  const badges: string[] = []
  if (point.is_break_point) badges.push('破发点')
  if (point.is_set_point) badges.push('盘点')
  if (point.is_match_point) badges.push('赛点')
  return badges
}

export function MatchPointsTimeline({
  points,
  players,
}: {
  points: PointEventDto[]
  players: [PlayerDto, PlayerDto]
}) {
  const games = useMemo<GameGroup[]>(() => {
    const byGame = new Map<string, GameGroup>()
    for (const point of points) {
      const key = `${point.set_number}-${point.game_number}`
      const group = byGame.get(key) ?? {
        setNumber: point.set_number,
        gameNumber: point.game_number,
        points: [],
      }
      group.points.push(point)
      byGame.set(key, group)
    }
    return [...byGame.values()].sort(
      (a, b) => a.setNumber - b.setNumber || a.gameNumber - b.gameNumber,
    )
  }, [points])

  const currentSet = games.length > 0 ? games[games.length - 1].setNumber : 0
  const currentGame = games.length > 0 ? games[games.length - 1].gameNumber : 0
  const [openSections, setOpenSections] = useState<Record<string, boolean>>({})
  const [hasNewPoints, setHasNewPoints] = useState(false)
  const scrollerRef = useRef<HTMLDivElement>(null)
  const previousCountRef = useRef(points.length)
  const nearBottomRef = useRef(true)

  const isOpen = (group: GameGroup) => {
    const key = `${group.setNumber}-${group.gameNumber}`
    const explicit = openSections[key]
    if (explicit !== undefined) return explicit
    return group.setNumber === currentSet && group.gameNumber === currentGame
  }

  const toggle = (group: GameGroup) => {
    const key = `${group.setNumber}-${group.gameNumber}`
    setOpenSections((current) => ({ ...current, [key]: !isOpen(group) }))
  }

  useEffect(() => {
    const scroller = scrollerRef.current
    const previousCount = previousCountRef.current
    previousCountRef.current = points.length
    if (!scroller || points.length <= previousCount) return
    if (nearBottomRef.current) {
      scroller.scrollTop = scroller.scrollHeight
    } else {
      setHasNewPoints(true)
    }
  }, [points.length])

  const onScroll = () => {
    const scroller = scrollerRef.current
    if (!scroller) return
    nearBottomRef.current =
      scroller.scrollHeight - scroller.scrollTop - scroller.clientHeight <= NEAR_BOTTOM_PX
    if (nearBottomRef.current) setHasNewPoints(false)
  }

  const jumpToLatest = () => {
    const scroller = scrollerRef.current
    if (!scroller) return
    scroller.scrollTop = scroller.scrollHeight
    nearBottomRef.current = true
    setHasNewPoints(false)
  }

  if (points.length === 0) {
    return (
      <p className="rounded-lg bg-muted/25 p-4 text-sm text-muted-foreground">
        逐分数据暂未提供；开赛后逐分事件会在此按盘/局展开。
      </p>
    )
  }

  const hasCorrection = points.some((point) => point.revision > 1)
  const setNumbers = [...new Set(games.map((group) => group.setNumber))].sort((a, b) => a - b)

  return (
    <div className="relative flex flex-col gap-3">
      {hasCorrection ? (
        <p
          role="status"
          aria-label="数据已校准"
          className="rounded-md bg-secondary/60 px-3 py-1.5 text-xs text-muted-foreground"
        >
          数据已校准：部分逐分记录被供应商修正，已按最新版本展示。
        </p>
      ) : null}

      {hasNewPoints ? (
        <button
          type="button"
          onClick={jumpToLatest}
          className="absolute -top-2 left-1/2 z-10 -translate-x-1/2 rounded-full bg-primary px-3 py-1 text-xs font-medium text-primary-foreground"
        >
          有新分 ↓
        </button>
      ) : null}

      <div
        ref={scrollerRef}
        data-points-scroller
        onScroll={onScroll}
        className="flex max-h-96 flex-col gap-3 overflow-y-auto pr-1"
      >
        {setNumbers.map((setNumber) => {
          const setGames = games.filter((group) => group.setNumber === setNumber)
          const setOpen = openSections[`set-${setNumber}`] ?? setNumber === currentSet
          return (
            <section key={setNumber} aria-label={`第 ${setNumber} 盘`}>
              <button
                type="button"
                aria-expanded={setOpen}
                onClick={() =>
                  setOpenSections((current) => ({
                    ...current,
                    [`set-${setNumber}`]: !setOpen,
                  }))
                }
                className="flex w-full items-center justify-between rounded-md bg-muted/30 px-3 py-2 text-sm font-medium"
              >
                第 {setNumber} 盘
                <ChevronDown
                  aria-hidden="true"
                  className={cn('size-4 transition-transform', setOpen && 'rotate-180')}
                />
              </button>
              {setOpen ? (
                <div className="mt-2 flex flex-col gap-2 pl-2">
                  {setGames.map((group) => {
                    const gameOpen = isOpen(group)
                    return (
                      <div key={`${group.setNumber}-${group.gameNumber}`}>
                        <button
                          type="button"
                          aria-expanded={gameOpen}
                          onClick={() => toggle(group)}
                          className="flex w-full items-center justify-between rounded-md px-2 py-1.5 text-xs text-muted-foreground"
                        >
                          第 {group.gameNumber} 局
                          <ChevronDown
                            aria-hidden="true"
                            className={cn('size-3.5 transition-transform', gameOpen && 'rotate-180')}
                          />
                        </button>
                        {gameOpen ? (
                          <ol className="mt-1 flex flex-col divide-y rounded-md bg-muted/20">
                            {group.points.map((point) => {
                              const winner =
                                point.winner_player_id === players[0].id
                                  ? players[0]
                                  : point.winner_player_id === players[1].id
                                    ? players[1]
                                    : null
                              const badges = keyPointBadges(point)
                              return (
                                <li
                                  key={point.id}
                                  className="flex items-center justify-between gap-2 px-3 py-2 text-sm"
                                >
                                  <span className="flex min-w-0 items-center gap-2">
                                    <span className="truncate font-medium">
                                      {winner ? shortName(winner.name) : '胜者待定'}
                                    </span>
                                    {badges.map((badge) => (
                                      <Badge key={badge} variant="outline">
                                        {badge}
                                      </Badge>
                                    ))}
                                  </span>
                                  <span className="font-mono text-xs text-muted-foreground tabular-nums">
                                    {pointScore(point)}
                                  </span>
                                </li>
                              )
                            })}
                          </ol>
                        ) : null}
                      </div>
                    )
                  })}
                </div>
              ) : null}
            </section>
          )
        })}
      </div>
    </div>
  )
}
