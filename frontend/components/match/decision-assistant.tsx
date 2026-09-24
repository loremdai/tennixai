'use client'

import { useState, type KeyboardEvent } from 'react'
import { BrainCircuit, Send, Sparkles } from 'lucide-react'

import type { DecisionPreview } from '@/components/p3/p3-preview-data'
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
import {
  InputGroup,
  InputGroupAddon,
  InputGroupButton,
  InputGroupInput,
} from '@/components/ui/input-group'

const prompts = ['为什么会有这个判断？', '这个价格怎么算的？', '什么情况下会暂停？']

function explain(question: string, decision: DecisionPreview): string {
  if (question.includes('价格') || question.includes('$10')) {
    return decision.executableProbability === null
      ? '目前没有足够的市场报价，暂时无法估算这个价格。'
      : `按 10 美元模拟金额，结合市场上的实际买卖报价估算为 ${(decision.executableProbability * 100).toFixed(1)}%。买入价和卖出价分别计算。`
  }
  if (question.includes('失效') || question.includes('撤销')) {
    return '如果比赛数据更新中断、报价更新较慢、可交易金额不足，或暂未提供胜率估算，就会暂停新的模拟操作，并保留上次有效数据。'
  }
  return `${decision.reason} 胜率由模型估算，市场价格会随比赛进程和交易情况变化。`
}

export function DecisionAssistant({ decision }: { decision: DecisionPreview }) {
  const [prompt, setPrompt] = useState('')
  const [answer, setAnswer] = useState<string | null>(null)
  const [question, setQuestion] = useState<string | null>(null)

  function submit(value: string) {
    const nextQuestion = value.trim()
    if (!nextQuestion) return
    setQuestion(nextQuestion)
    setAnswer(explain(nextQuestion, decision))
    setPrompt('')
  }

  function handleKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key !== 'Enter') return
    if (event.nativeEvent.isComposing || event.keyCode === 229) return
    event.preventDefault()
    submit(prompt)
  }

  return (
    <Card id="decision-assistant" data-tone="assistant" className="scroll-mt-24">
      <CardHeader>
        <CardTitle><h2>本场判断助手</h2></CardTitle>
        <p className="text-sm text-muted-foreground">了解这场比赛的估算结果、市场价格和模拟记录</p>
        <CardAction>
          <Badge variant="secondary"><Sparkles data-icon="inline-start" aria-hidden="true" />判断说明</Badge>
        </CardAction>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <div className="flex flex-wrap gap-2" aria-label="决策解释示例问题">
          {prompts.map((item) => (
            <Button key={item} variant="outline" size="sm" onClick={() => submit(item)}>{item}</Button>
          ))}
        </div>
        <div aria-live="polite">
          {answer ? (
            <article className="rounded-lg bg-muted/35 p-4">
              <div className="flex items-center gap-2 text-sm font-medium text-primary">
                  <BrainCircuit aria-hidden="true" className="size-4" />基于当前比赛信息
              </div>
              <p className="mt-3 text-sm font-medium">“{question}”</p>
              <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{answer}</p>
            </article>
          ) : (
            <div className="flex min-h-28 flex-col items-center justify-center gap-2 rounded-lg border border-dashed bg-muted/15 p-4 text-center">
              <BrainCircuit aria-hidden="true" className="size-5 text-primary" />
              <p className="text-sm font-medium">可以问为什么这样判断，或报价代表什么</p>
            </div>
          )}
        </div>
      </CardContent>
      <CardFooter>
        <form className="w-full" onSubmit={(event) => { event.preventDefault(); submit(prompt) }}>
          <label htmlFor="decision-question" className="sr-only">向 Tennix 询问本场决策</label>
          <InputGroup className="h-11">
            <InputGroupInput
              id="decision-question"
              value={prompt}
              onChange={(event) => setPrompt(event.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="例如：模型为什么看好这位球员？"
              autoComplete="off"
            />
            <InputGroupAddon align="inline-end">
              <InputGroupButton type="submit" size="icon-sm" aria-label="发送问题"><Send aria-hidden="true" /></InputGroupButton>
            </InputGroupAddon>
          </InputGroup>
        </form>
      </CardFooter>
    </Card>
  )
}
