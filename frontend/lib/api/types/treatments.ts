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
  start_date: string
  end_date: string | null
  dose: string | null
  notes: string | null
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface TreatmentCreate {
  name: string
  type: TreatmentType
  start_date: string
  end_date?: string | null
  dose?: string | null
  notes?: string | null
}

export interface TreatmentUpdate {
  name?: string
  type?: TreatmentType
  start_date?: string
  end_date?: string | null
  dose?: string | null
  notes?: string | null
}
