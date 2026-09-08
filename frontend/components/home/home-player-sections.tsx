'use client'

import { BellOff } from 'lucide-react'

import { SectionHeading } from '@/components/home/section-heading'
import { Badge } from '@/components/ui/badge'
import {
  Card,
  CardAction,
  CardContent,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'

export function FollowedPlayersSection() {
  return (
    <section id="players" className="flex scroll-mt-24 flex-col gap-4" aria-labelledby="players-title">
      <SectionHeading
        headingId="players-title"
        eyebrow="YOUR WATCHLIST"
        title="关注球员"
        description="关注列表将在后续阶段接入。"
        action={<Badge variant="outline">后续阶段</Badge>}
      />
      <Card size="sm">
        <CardHeader>
          <div className="flex min-w-0 items-center gap-3">
            <div className="flex size-11 items-center justify-center rounded-full bg-secondary text-primary">
              <BellOff aria-hidden="true" className="size-4" />
            </div>
            <div className="min-w-0">
              <CardTitle>
                <h3 className="truncate text-sm">关注功能将在后续阶段接入</h3>
              </CardTitle>
              <p className="mt-1 text-xs text-muted-foreground">
                P1 不提供球员关注与提醒；比赛事实均来自 Tennix 结构化数据。
              </p>
            </div>
          </div>
        </CardHeader>
      </Card>
    </section>
  )
}

export function RecentResultsCard() {
  return (
    <Card id="results" className="scroll-mt-24">
      <CardHeader>
        <CardTitle>
          <h2>Recent Results</h2>
        </CardTitle>
        <p className="text-sm text-muted-foreground">历史赛果</p>
        <CardAction>
          <Badge variant="outline">P1</Badge>
        </CardAction>
      </CardHeader>
      <CardContent className="flex flex-col">
        <article className="flex flex-col gap-3 py-1">
          <p className="text-sm leading-relaxed text-muted-foreground">
            P1 暂不支持历史赛果
          </p>
          <p className="text-xs leading-relaxed text-muted-foreground">
            当前阶段只提供今日、今晚与正在进行的比赛信息；历史结果查询将返回明确的“暂不支持”。
          </p>
        </article>
      </CardContent>
    </Card>
  )
}
