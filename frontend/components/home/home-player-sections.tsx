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
        eyebrow="球员关注"
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
                目前还不能关注球员或接收提醒，之后开放时会在这里说明。
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
          <h2>近期赛果</h2>
        </CardTitle>
        <p className="text-sm text-muted-foreground">历史赛果</p>
        <CardAction>
          <Badge variant="outline">暂未提供</Badge>
        </CardAction>
      </CardHeader>
      <CardContent className="flex flex-col">
        <article className="flex flex-col gap-3 py-1">
          <p className="text-sm leading-relaxed text-muted-foreground">
            历史赛果暂不可查
          </p>
          <p className="text-xs leading-relaxed text-muted-foreground">
            这里目前只展示今天及即将开始的比赛。球员历史赛果可在个人主页查看。
          </p>
        </article>
      </CardContent>
    </Card>
  )
}
