export type TrackerKind = 'counter' | 'binary'

export interface Tracker {
  id: number
  name: string
  kind: TrackerKind
  icon: string | null
  unit: string | null
  position: number
  archived: boolean
  is_seed: boolean
  created_at: string
}

export interface TrackerValue {
  tracker_id: number
  date: string
  value: number
  updated_at: string
}

export interface TrackerCreate {
  name: string
  kind: TrackerKind
  icon?: string | null
  unit?: string | null
  position?: number
}

export interface TrackerUpdate {
  name?: string
  icon?: string | null
  unit?: string | null
  position?: number
  archived?: boolean
}
