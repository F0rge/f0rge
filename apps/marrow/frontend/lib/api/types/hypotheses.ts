export type HypothesisStatus = 'live' | 'weakening' | 'killed' | 'parked'

export interface Hypothesis {
  id: string
  slug: string
  title: string
  status: HypothesisStatus
  layer: 1 | 2 | null
  kill_test: string | null
  next_move: string | null
  last_evidence: string | null
  cite: string | null
  sort_order: number
  created_at: string
  updated_at: string
}

export interface HypothesisCreate {
  slug: string
  title: string
  status?: HypothesisStatus
  layer?: 1 | 2 | null
  kill_test?: string | null
  next_move?: string | null
  last_evidence?: string | null
  cite?: string | null
  sort_order?: number
}

export interface HypothesisUpdate {
  slug?: string
  title?: string
  status?: HypothesisStatus
  layer?: 1 | 2 | null
  kill_test?: string | null
  next_move?: string | null
  last_evidence?: string | null
  cite?: string | null
  sort_order?: number
}

export interface NOf1Slot {
  id: string
  change: string
  start: string
  watch_field: string
  stop_rule: string
  created_at: string
  updated_at: string
}

export interface NOf1Upsert {
  change: string
  start: string
  watch_field: string
  stop_rule: string
}
