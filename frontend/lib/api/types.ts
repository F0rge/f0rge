export interface Photo {
  id: number
  entry_id: number
  filename: string
  label: string | null
  created_at: string
}

export interface Entry {
  id: number
  date: string // YYYY-MM-DD
  overall: number // 1-3 (Very Poor, Standard, Very Good)
  bloating: number // 0-3
  stool_normal: boolean
  joint_pain: number // 0-3
  neuro: number // -1, 0, 1
  sleep_quality: number // 1-3
  stress: number // 1-3
  diet_risk: 'normal' | 'high-histamine' | 'high-fodmap' | 'gluten' | 'both' | 'not-sure'
  supplements: string // comma-separated supplement IDs
  sick: boolean
  notes: string | null
  photos: Photo[]
  created_at: string
  updated_at: string
}

export interface EntryCreate {
  date: string
  overall: number
  bloating: number
  stool_normal: boolean
  joint_pain: number
  neuro: number
  sleep_quality: number
  stress: number
  diet_risk: string
  supplements: string
  sick: boolean
  notes?: string
}

export interface AuthUser {
  authenticated: boolean
}
