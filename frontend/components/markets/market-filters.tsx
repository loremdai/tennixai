import { RotateCcw } from 'lucide-react'

import { Button } from '@/components/ui/button'
import type { CircuitTier, Gender, MarketPhase } from '@/lib/api/types'

export type GenderFilter = Gender | 'all'
export type PhaseFilter = MarketPhase | 'all'

const tierOptions: Array<{ value: CircuitTier; label: string }> = [
  { value: 'atp', label: 'ATP' },
  { value: 'wta', label: 'WTA' },
  { value: 'challenger', label: 'Challenger' },
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
  { value: 'prematch', label: '赛前' },
  { value: 'live', label: '直播' },
  { value: 'closed', label: '已收盘' },
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
      variant={active ? 'secondary' : 'outline'}
      size="lg"
      aria-pressed={active}
      onClick={onClick}
      className="h-11 md:h-9"
    >
      {children}
    </Button>
  )
}

/** Canonical P3 filters with the approved v0 geometry. Values are the
 * backend's canonical enums; filtering is applied to server-provided rows. */
export function MarketFilters({
  tiers,
  gender,
  phase,
  onTiersChange,
  onGenderChange,
  onPhaseChange,
  onReset,
}: {
  tiers: CircuitTier[]
  gender: GenderFilter
  phase: PhaseFilter
  onTiersChange: (tiers: CircuitTier[]) => void
  onGenderChange: (gender: GenderFilter) => void
  onPhaseChange: (phase: PhaseFilter) => void
  onReset: () => void
}) {
  const hasFilters = tiers.length > 0 || gender !== 'all' || phase !== 'all'
  return (
    <section className="flex flex-col gap-4" aria-label="市场筛选">
      <div className="flex flex-col gap-3 rounded-xl border bg-card/65 p-4">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h2 className="font-semibold">市场筛选</h2>
            <p className="mt-1 text-sm text-muted-foreground">级别、组别与阶段可以叠加；筛选状态写入 URL。</p>
          </div>
          {hasFilters ? (
            <Button variant="ghost" size="sm" onClick={onReset}>
              <RotateCcw data-icon="inline-start" aria-hidden="true" />
              重置
            </Button>
          ) : null}
        </div>

        <div className="flex flex-col gap-3">
          <fieldset>
            <legend className="mb-2 text-xs font-medium text-muted-foreground">赛事级别</legend>
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
          <div className="grid gap-3 sm:grid-cols-2">
            <fieldset>
              <legend className="mb-2 text-xs font-medium text-muted-foreground">组别</legend>
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
            <fieldset>
              <legend className="mb-2 text-xs font-medium text-muted-foreground">比赛阶段</legend>
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
          </div>
        </div>
      </div>
    </section>
  )
}
