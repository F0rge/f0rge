export type TreatmentType =
  | 'antibiotic'
  | 'antimicrobial'
  | 'prescription'
  | 'intervention'
  | 'protocol'
  | 'other'

export interface Treatment {
  id: number
  name: string
  normalized_name: string
  type: TreatmentType
  group_name: string | null
  start_date: string
  end_date: string | null
  dose: string | null
  doses_per_day: number | null
  notes: string | null
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface TreatmentCreate {
  name: string
  type: TreatmentType
  group_name?: string | null
  start_date: string
  end_date?: string | null
  dose?: string | null
  doses_per_day?: number | null
  notes?: string | null
}

export interface TreatmentUpdate {
  name?: string
  type?: TreatmentType
  group_name?: string | null
  start_date?: string
  end_date?: string | null
  dose?: string | null
  doses_per_day?: number | null
  notes?: string | null
}

export interface TreatmentLogResponse {
  treatment_id: number
  date: string
  doses_taken: number
  updated_at: string
}

export interface ProtocolItem {
  id: number
  name: string
  dose: string | null
  doses_per_day: number | null
  doses_taken: number
  day_num: number
}

export interface ProtocolToday {
  doses_taken: number
  doses_planned: number
  pct: number
}

export interface ProtocolResponse {
  items: ProtocolItem[]
  today: ProtocolToday
  streak: number
  best_streak: number
}
