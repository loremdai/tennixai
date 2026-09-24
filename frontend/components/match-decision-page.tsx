'use client'

import { useState } from 'react'

import { DecisionAssistant } from '@/components/match/decision-assistant'
import { DecisionEvidence } from '@/components/match/decision-evidence'
import { DecisionSummary } from '@/components/match/decision-summary'
import { MatchHero } from '@/components/match/match-hero'
import { OverviewCard, ScoreProgressCard, StatsCard } from '@/components/match/match-main'
import type { MatchStatus } from '@/components/match/match-data'
import { MatchMomentumCard } from '@/components/match/match-momentum'
import { KeyFactsCard } from '@/components/match/match-sidebar'
import { PaperLifecycle } from '@/components/match/paper-lifecycle'
import { ProbabilityMarketTrajectory } from '@/components/match/probability-market-trajectory'
import { buildPreviewMatch } from '@/components/match/match-preview-data'
import { ProductHeader } from '@/components/match/match-header'
import { P3PreviewControls } from '@/components/p3/p3-preview-controls'
import {
  getDecisionPreview,
  type AnalysisState,
  type ConfidenceState,
  type DecisionOverlay,
  type DecisionState,
  type MethodologyState,
  type SelectionState,
} from '@/components/p3/p3-preview-data'

export function MatchDecisionPage({
  initialStatus,
  initialState,
  initialSelection,
  initialOverlay,
  initialAnalysis,
  initialMethodology,
  initialConfidence,
}: {
  initialStatus: MatchStatus
  initialState: DecisionState
  initialSelection: SelectionState
  initialOverlay: DecisionOverlay
  initialAnalysis: AnalysisState
  initialMethodology: MethodologyState
  initialConfidence: ConfidenceState
}) {
  const [state, setState] = useState(initialState)
  const [selection, setSelection] = useState(initialSelection)
  const [overlay, setOverlay] = useState(initialOverlay)
  const [analysis, setAnalysis] = useState(initialAnalysis)
  const [methodology, setMethodology] = useState(initialMethodology)
  const [confidence, setConfidence] = useState(initialConfidence)
  const match = buildPreviewMatch(initialStatus)
  const decision = getDecisionPreview(state, overlay, confidence, selection)

  function changeControl(key: string, value: string) {
    const url = new URL(window.location.href)
    url.searchParams.set('preview', 'p3')
    url.searchParams.set(key, value)
    window.history.replaceState(null, '', url)

    if (key === 'state') setState(value as DecisionState)
    if (key === 'selection') setSelection(value as SelectionState)
    if (key === 'overlay') setOverlay(value as DecisionOverlay)
    if (key === 'analysis') setAnalysis(value as AnalysisState)
    if (key === 'methodology') setMethodology(value as MethodologyState)
    if (key === 'confidence') setConfidence(value as ConfidenceState)
  }

  function focusDecisionAssistant() {
    document.getElementById('decision-assistant')?.scrollIntoView({ behavior: 'smooth', block: 'center' })
    window.setTimeout(() => document.getElementById('decision-question')?.focus(), 350)
  }

  return (
    <div className="min-h-screen bg-background text-foreground">
      <a href="#match-decision-content" className="sr-only fixed left-3 top-3 z-50 rounded-lg bg-primary px-3 py-2 text-sm font-medium text-primary-foreground focus:not-sr-only">跳至主要内容</a>
      <ProductHeader active="live" marketsHref="/markets?preview=p3" />

      <main id="match-decision-content" className="mx-auto flex w-full max-w-7xl flex-col gap-4 px-4 py-5 md:px-6 md:py-7">
        <P3PreviewControls
          title="比赛判断演示"
          description="以下为示例比赛和模拟报价，不代表实时赛况或真实交易。"
          fields={[
            {
              key: 'state',
              label: '判断状态',
              value: state,
              options: [
                { value: 'market_only', label: '仅显示市场报价' },
                { value: 'no_bet', label: '暂不参与' },
                { value: 'wait', label: '等待更好价格' },
                { value: 'buy', label: '模拟买入机会' },
                { value: 'entry_pending', label: '等待买入确认' },
                { value: 'missed', label: '未模拟买入' },
                { value: 'hold', label: '模拟持有中' },
                { value: 'sell', label: '模拟退出机会' },
                { value: 'exit_pending', label: '等待退出确认' },
                { value: 'exited', label: '已模拟退出' },
                { value: 'exit_missed', label: '退出未成交' },
                { value: 'settled', label: '已结算' },
              ],
            },
            {
              key: 'selection',
              label: '选择',
              value: selection,
              options: [
                { value: 'sinner', label: 'Sinner' },
                { value: 'alcaraz', label: 'Alcaraz' },
              ],
            },
            {
              key: 'overlay',
              label: '数据状态',
              value: overlay,
              options: [
                { value: 'none', label: '正常' },
                { value: 'stale', label: '报价更新较慢' },
                { value: 'gap', label: '比赛数据更新中断' },
              ],
            },
            {
              key: 'analysis',
              label: '走势曲线',
              value: analysis,
              options: [
                { value: 'expanded', label: '显示' },
                { value: 'collapsed', label: '隐藏' },
              ],
            },
            {
              key: 'methodology',
              label: '详细说明',
              value: methodology,
              options: [
                { value: 'collapsed', label: '折叠' },
                { value: 'open', label: '展开' },
              ],
            },
            {
              key: 'confidence',
              label: '估算范围',
              value: confidence,
              options: [
                { value: 'high', label: '较窄' },
                { value: 'medium', label: '一般' },
                { value: 'low', label: '较宽' },
                { value: 'empty', label: '数据不足' },
                { value: 'error', label: '暂不可用' },
              ],
            },
          ]}
          onChange={changeControl}
        />

        <MatchHero match={match} highlight={null} onAsk={focusDecisionAssistant} preview />
        <DecisionSummary decision={decision} onAsk={focusDecisionAssistant} />

        <div className="grid min-w-0 items-start gap-4 lg:grid-cols-[minmax(0,1fr)_22rem]">
          <div className="min-w-0 lg:col-start-1 lg:row-start-2">
            <ScoreProgressCard match={match} preview highlight={null} />
          </div>
          <aside className="min-w-0 lg:col-start-2 lg:row-start-2" aria-label="比赛关键事实">
            <KeyFactsCard match={match} preview />
          </aside>
          <div className="min-w-0 lg:col-start-1 lg:row-start-1">
            <OverviewCard match={match} preview />
          </div>
          <div className="min-w-0 lg:col-start-1 lg:row-start-3">
            <ProbabilityMarketTrajectory decision={decision} analysisState={analysis} />
          </div>
          <div className="min-w-0 lg:col-start-1 lg:row-start-4">
            <DecisionEvidence decision={decision} methodologyState={methodology} />
          </div>
          <div className="min-w-0 lg:col-start-1 lg:row-start-5">
            <StatsCard match={match} preview highlight={null} snapshot={null} />
          </div>
          <div className="min-w-0 lg:col-start-1 lg:row-start-6">
            <MatchMomentumCard match={match} preview highlight={null} snapshot={null} />
          </div>
          <div className="min-w-0 lg:col-start-1 lg:row-start-7">
            <PaperLifecycle decision={decision} />
          </div>
          <aside className="min-w-0 lg:sticky lg:top-20 lg:col-start-2 lg:row-start-1" aria-label="比赛决策助手">
            <DecisionAssistant key={`${state}-${overlay}-${selection}-${confidence}`} decision={decision} />
          </aside>
        </div>
      </main>

      <footer className="border-t">
        <div className="mx-auto flex max-w-7xl flex-col justify-between gap-2 px-4 py-6 text-sm text-muted-foreground sm:flex-row md:px-6">
          <span>Tennix · 比赛智能，逐分解释</span>
          <span>示例数据仅用于页面演示 · 不涉及真实交易</span>
        </div>
      </footer>
    </div>
  )
}
