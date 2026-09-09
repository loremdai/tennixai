'use client'

import { RotateCcw } from 'lucide-react'

import { Button } from '@/components/ui/button'
import type { CircuitTier, Discipline, Gender } from '@/lib/api/types'
import {
  CIRCUIT_LABELS,
  CIRCUIT_ORDER,
  DISCIPLINE_LABELS,
  DISCIPLINE_ORDER,
  GENDER_LABELS,
  GENDER_ORDER,
  isDefaultFilters,
  toggleFilterValue,
  type FacetGroup,
  type MatchFiltersState,
} from '@/lib/match-filters'

export type FacetCountsState = {
  circuits: Record<CircuitTier, number>
  genders: Record<Gender, number>
  disciplines: Record<Discipline, number>
}

type GroupConfig = {
  group: FacetGroup
  label: string
  values: string[]
  labels: Record<string, string>
}

const GROUPS: GroupConfig[] = [
  { group: 'circuits', label: '赛事级别', values: CIRCUIT_ORDER, labels: CIRCUIT_LABELS },
  { group: 'genders', label: '性别', values: GENDER_ORDER, labels: GENDER_LABELS },
  { group: 'disciplines', label: '单双打', values: DISCIPLINE_ORDER, labels: DISCIPLINE_LABELS },
]

export function MatchFiltersBar({
  filters,
  facetCounts,
  onChange,
  onReset,
}: {
  filters: MatchFiltersState
  facetCounts: FacetCountsState | null
  onChange: (next: MatchFiltersState) => void
  onReset: () => void
}) {
  const showReset = !isDefaultFilters(filters)

  return (
    <div className="flex flex-col gap-2 rounded-xl border bg-card/65 p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">筛选</p>
        {showReset ? (
          <Button variant="ghost" size="sm" onClick={onReset}>
            <RotateCcw data-icon="inline-start" aria-hidden="true" />
            恢复默认
          </Button>
        ) : null}
      </div>
      <div className="flex flex-col gap-2 lg:flex-row lg:items-center lg:gap-4">
        {GROUPS.map((config) => {
          const active = filters[config.group] as string[]
          const counts = facetCounts ? facetCounts[config.group] : null
          return (
            <div
              key={config.group}
              role="group"
              aria-label={config.label}
              className="flex flex-wrap items-center gap-1.5"
            >
              <span className="text-xs text-muted-foreground lg:sr-only">{config.label}</span>
              {config.values.map((value) => {
                const isActive = active.includes(value)
                const count = counts ? counts[value as keyof typeof counts] ?? 0 : null
                const disabled = count === 0 && !isActive
                const accessibleName =
                  count === null
                    ? config.labels[value]
                    : `${config.labels[value]}（${count} 场）`
                return (
                  <Button
                    key={value}
                    type="button"
                    variant={isActive ? 'default' : 'outline'}
                    size="sm"
                    aria-pressed={isActive}
                    aria-label={accessibleName}
                    disabled={disabled}
                    onClick={() => onChange(toggleFilterValue(filters, config.group, value))}
                  >
                    {config.labels[value]}
                    {count === null ? null : (
                      <span aria-hidden="true" className="ml-1 text-xs opacity-70 tabular-nums">
                        {count}
                      </span>
                    )}
                  </Button>
                )
              })}
            </div>
          )
        })}
      </div>
    </div>
  )
}
