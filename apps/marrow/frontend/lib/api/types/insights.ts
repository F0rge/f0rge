export interface TrendPoint {
  date: string
  value: number | null
  rolling_avg_7: number | null
}

export interface TrendSeries {
  key: string
  label: string
  category: string
  points: TrendPoint[]
  current: number | null
  rolling_avg_7: number | null
  delta_30d: number | null
}

export interface TrendsResponse {
  series: TrendSeries[]
}

export interface TreatmentResponseRow {
  treatment_id: number
  name: string
  type: string
  start_date: string
  end_date: string | null
  baseline_mean: number | null
  during_mean: number | null
  after_mean: number | null
  baseline_n: number
  during_n: number
  after_n: number
  delta_during_vs_baseline: number | null
}

export interface TreatmentResponseList {
  outcome: string
  rows: TreatmentResponseRow[]
}
