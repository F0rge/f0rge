/** Hand-written types for GET /api/v1/signals — not health-signals (weather). */

import type { TrendPoint } from './insights'

export type GoodDirection = 'up' | 'down' | null

export interface SignalsMeta {
  days_total: number
  days_usable: number
  warmup: number
  drop_reasons: Record<string, number>
  insufficient_data: boolean
  insufficient_reason: string | null
  outcome: string
  start: string | null
  end: string | null
}

export interface SignalsModel {
  mae: number | null
  baseline_mae: number | null
  noise_floor_mae: number | null
  noise_sd: number | null
  skill: number | null
  holdout_rmse: number | null
  holdout_r2: number | null
  r2_basis: string | null
  relearning: boolean
  relearning_message: string | null
}

export interface TodayContribution {
  label: string
  detail: string | null
  display_value: number
  driver_id: string
}

export interface TodayCalibrationPoint {
  date: string
  predicted: number
  actual: number | null
}

export interface SignalsToday {
  baseline: number | null
  contributions: TodayContribution[]
  predicted: number | null
  band_low: number | null
  band_high: number | null
  band_level: number | null
  actual: number | null
  residual: number | null
  calibration_series: TodayCalibrationPoint[]
}

export interface DoseBin {
  label: string
  n: number
  mean: number | null
}

export interface DayStrips {
  exposed: (number | null)[]
  unexposed: (number | null)[]
}

export interface SignalsDriver {
  feature: string
  label: string
  feature_class: string
  shape: string
  theta_hat: number | null
  ci_low: number | null
  ci_high: number | null
  tier: string
  reason: string
  exposed_days: number
  unexposed_days: number
  exposed_runs: number
  dose_table: DoseBin[]
  day_strips: DayStrips
  good_direction: GoodDirection
  se_ratio: number | null
}

export interface SignalsMirror {
  feature: string
  label: string
  rho: number | null
  n: number
  reason: string
}

export interface UnexplainedEpisode {
  dates: string[]
  start_date: string
  end_date: string
  direction: string
  max_abs_residual: number
}

export interface TrackerProposal {
  tracker_id: string
  label: string
  days_covered: number
}

export interface SignalsUnexplained {
  unexplained_bad: UnexplainedEpisode[]
  unexplained_good: UnexplainedEpisode[]
  couldnt_score: string[]
  relearning: boolean
  relearning_message: string
  tracker_proposals: TrackerProposal[]
}

export interface SignalsTrendSeries {
  key: string
  label: string
  category: string
  points: TrendPoint[]
  current: number | null
  rolling_avg_7: number | null
  delta_30d: number | null
  good_direction: GoodDirection
}

export interface SignalsTrends {
  series: SignalsTrendSeries[]
}

export interface SignalsResponse {
  meta: SignalsMeta
  model: SignalsModel
  today: SignalsToday
  drivers: SignalsDriver[]
  mirrors: SignalsMirror[]
  unexplained: SignalsUnexplained
  trends: SignalsTrends
}

/** Raw driver shape from JSON (`class` alias for feature_class). */
export type SignalsDriverJson = Omit<SignalsDriver, 'feature_class'> & { class: string }
