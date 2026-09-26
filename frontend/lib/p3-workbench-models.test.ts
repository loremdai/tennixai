import { describe, expect, it } from 'vitest'

import type { DecisionSnapshotDto } from '@/lib/api/types'
import { toDecisionSummaryModel } from './p3-workbench-models'

const NOW = new Date('2026-09-26T02:00:00Z')

const snapshot: DecisionSnapshotDto = {
  match_id: 'mat_1',
  market_id: 'mkt_1',
  action: 'hold',
  reason_code: null,
  target_player_id: 'ply_1',
  observation_version: 1,
  model_probabilities: { ply_1: 0.62, ply_2: 0.38 },
  model_availability: 'available',
  quote_average_price: '0.55',
  quote_side: 'exit',
  conservative_net_edge: '0.07',
  max_acceptable_price: null,
  hold_value: null,
  model_version: 'model-v1',
  calibration_version: 'cal-v1',
  policy_version: 'policy-v1',
  data_version: 'data-v1',
  gates: [],
  outcome_levels: [],
  position: null,
  lifecycle: [],
  is_stale: false,
  has_gap: false,
  lock_profit_available: false,
  as_of: '2026-09-26T02:00:00Z',
}

describe('toDecisionSummaryModel', () => {
  it('keeps selected English and localized names separate', () => {
    const model = toDecisionSummaryModel(
      snapshot,
      'Jannik Sinner',
      NOW,
      '扬尼克·辛纳',
    )

    expect(model.selectionLabel).toBe('Jannik Sinner')
    expect(model.selectionLocalizedName).toBe('扬尼克·辛纳')
  })
})
