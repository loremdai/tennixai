import { useId, useState } from 'react'
import { ChevronDown, RotateCcw, SlidersHorizontal } from 'lucide-react'

import { Button } from '@/components/ui/button'
import type { CircuitTier, Gender, MarketPhase } from '@/lib/api/types'

export type GenderFilter = Gender | 'all'
export type PhaseFilter = MarketPhase | 'all'

const tierOptions: Array<{ value: CircuitTier; label: string }> = [
  { value: 'atp', label: 'ATP' },
  { value: 'wta', label: 'WTA' },
  { value: 'challenger', label: '挑战赛' },
  { value: 'itf', label: 'ITF' },
  { value: 'other', label: '其他' },
]

const genderOptions: Array<{ value: GenderFilter; label: string }> = [
  { value: 'all', label: '全部' },
  { value: 'men', label: '男子' },
  { value: 'women', label: '女子' },
]

const phaseOptions: Array<{ value: PhaseFilter; label: string }> = [
  { value: 'all', label: '全部' },
  { value: 'live', label: '进行中' },
  { value: 'prematch', label: '赛前' },
  { value: 'closed', label: '已结束' },
]

function FilterChip({
  active,
  children,
  onClick,
}: {
  active: boolean
  children: React.ReactNode
  onClick: () => void
}) {
  return (
    <Button
      type="button"
      variant="outline"
      size="lg"
      aria-pressed={active}
      onClick={onClick}
      className={active
        ? 'h-11 border-primary bg-primary/10 px-3 text-primary hover:bg-primary/15 hover:text-primary'
        : 'h-11 bg-background/35 px-3 text-muted-foreground hover:text-foreground'}
    >
      {children}
    </Button>
  )
}

/** Canonical P3 filters; changes refetch the first server page. */
export function MarketFilters({
  tiers,
  gender,
  phase,
  onTiersChange,
  onGenderChange,
  onPhaseChange,
  onReset,
  canReset,
}: {
  tiers: CircuitTier[]
  gender: GenderFilter
  phase: PhaseFilter
  onTiersChange: (tiers: CircuitTier[]) => void
  onGenderChange: (gender: GenderFilter) => void
  onPhaseChange: (phase: PhaseFilter) => void
  onReset: () => void
  canReset: boolean
}) {
  const [mobileOpen, setMobileOpen] = useState(false)
  const filterPanelId = useId()
  const activeCount =
    tiers.length + Number(gender !== 'all') + Number(phase !== 'all')

  return (
    <section className="flex flex-col gap-3 rounded-xl border border-foreground/10 bg-card/35 p-3 md:gap-4 md:p-4" aria-label="市场筛选">
      <div>
        <h2 className="text-lg font-semibold">市场筛选</h2>
        <p className="mt-1 text-sm text-muted-foreground">可同时按赛事级别、性别和比赛阶段筛选。</p>
      </div>
      <Button
        type="button"
        variant="outline"
        aria-expanded={mobileOpen}
        aria-controls={filterPanelId}
        onClick={() => setMobileOpen((open) => !open)}
        className="flex h-11 w-full items-center justify-between md:hidden"
      >
        <span className="flex items-center gap-2">
          <SlidersHorizontal aria-hidden="true" className="size-4" />
          筛选 · {activeCount} 项
        </span>
        <ChevronDown
          aria-hidden="true"
          className={`size-4 transition-transform ${mobileOpen ? 'rotate-180' : ''}`}
        />
      </Button>

      <div
        id={filterPanelId}
        className={`flex-col gap-3 md:flex md:flex-row md:flex-wrap md:items-center md:gap-2.5 xl:flex-nowrap ${mobileOpen ? 'flex' : 'hidden'}`}
      >
        <fieldset className="flex min-w-0 flex-col gap-2 sm:flex-row sm:items-center md:border-r md:pr-3">
          <legend className="sr-only">赛事级别</legend>
          <span aria-hidden="true" className="text-xs font-medium text-muted-foreground">赛事级别</span>
          <div className="flex flex-wrap gap-2">
            {tierOptions.map((option) => (
              <FilterChip
                key={option.value}
                active={tiers.includes(option.value)}
                onClick={() =>
                  onTiersChange(
                    tiers.includes(option.value)
                      ? tiers.filter((item) => item !== option.value)
                      : [...tiers, option.value],
                  )
                }
              >
                {option.label}
              </FilterChip>
            ))}
          </div>
        </fieldset>

        <fieldset className="flex min-w-0 flex-col gap-2 sm:flex-row sm:items-center md:border-r md:pr-3">
          <legend className="sr-only">性别</legend>
          <span aria-hidden="true" className="text-xs font-medium text-muted-foreground">性别</span>
          <div className="flex flex-wrap gap-2">
            {genderOptions.map((option) => (
              <FilterChip
                key={option.value}
                active={gender === option.value}
                onClick={() => onGenderChange(option.value)}
              >
                {option.label}
              </FilterChip>
            ))}
          </div>
        </fieldset>

        <fieldset className="flex min-w-0 flex-col gap-2 sm:flex-row sm:items-center md:border-r md:pr-3">
          <legend className="sr-only">比赛阶段</legend>
          <span aria-hidden="true" className="text-xs font-medium text-muted-foreground">比赛阶段</span>
          <div className="flex flex-wrap gap-2">
            {phaseOptions.map((option) => (
              <FilterChip
                key={option.value}
                active={phase === option.value}
                onClick={() => onPhaseChange(option.value)}
              >
                {option.label}
              </FilterChip>
            ))}
          </div>
        </fieldset>

        <Button
          type="button"
          variant="ghost"
          size="lg"
          className="h-11 self-start md:ml-auto md:self-center"
          onClick={onReset}
          disabled={!canReset}
        >
          <RotateCcw data-icon="inline-start" aria-hidden="true" />
          重置
        </Button>
      </div>
    </section>
  )
}
