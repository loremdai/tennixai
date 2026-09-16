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

const prompts = ['为什么是这个状态？', '$10 可执行价格是什么？', '什么会让建议失效？']

function explain(question: string, decision: DecisionPreview): string {
  if (question.includes('价格') || question.includes('$10')) {
    return decision.executableProbability === null
      ? '该快照没有可执行报价，因此不会用中间价或另一侧的补数代替。'
      : `目标方向按 $10 深度得到 ${(decision.executableProbability * 100).toFixed(1)}% 的可执行概率；两侧报价独立计算，不强制互补。`
  }
  if (question.includes('失效') || question.includes('撤销')) {
    return '超过 freshness 阈值、出现不可插值的数据 gap、流动性 gate 失败或模型覆盖不足时，基础动作会被撤销或降级；最后可信数字仍会保留并标时。'
  }
  return `${decision.stateLabel} 来自结构化 hard gates 与版本化模型：${decision.reason} 该助手只解释已生成的字段，不生成概率、价格或决策归因。`
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
        <CardTitle><h2>本场决策助手</h2></CardTitle>
        <p className="text-sm text-muted-foreground">解释当前结构化结论，不改写数值</p>
        <CardAction>
          <Badge variant="secondary"><Sparkles data-icon="inline-start" aria-hidden="true" />解释层</Badge>
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
                <BrainCircuit aria-hidden="true" className="size-4" />基于当前快照
              </div>
              <p className="mt-3 text-sm font-medium">“{question}”</p>
              <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{answer}</p>
            </article>
          ) : (
            <div className="flex min-h-28 flex-col items-center justify-center gap-2 rounded-lg border border-dashed bg-muted/15 p-4 text-center">
              <BrainCircuit aria-hidden="true" className="size-5 text-primary" />
              <p className="text-sm font-medium">询问 BUY / WAIT、报价口径或 hard gates</p>
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
              placeholder="例如：为什么现在是 BUY？"
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
