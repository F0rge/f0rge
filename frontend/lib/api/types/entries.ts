export interface Photo {
  id: number
  entry_id: number
  filename: string
  label: string | null
  meal_time: string | null
  created_at: string
}

export interface PhotoScores {
  histamine_load: number
  fodmap_count: number
  gluten_count: number
  dairy_count: number
}

export interface PhotoSignal {
  flags: string[]
  scores: PhotoScores
  sources: Record<string, string[]>
}

export type StoolStatus = 'normal' | 'abnormal' | 'none'

export interface Entry {
  id: number
  date: string // YYYY-MM-DD
  schema_version: number
  entry_time: string | null
  period_of_day: 'morning' | 'midday' | 'evening' | 'night' | null
  overall: number // 1-3 (Very Poor, Standard, Very Good)
  bloating: number // 0-3
  // v1 legacy
  stool_normal: boolean | null
  stool_type: string | null
  // v2
  stool_status: StoolStatus | null
  bristol_type: number | null // 1-7
  joint_pain: number // 0-3
  neuro: number // -1, 0, 1
  sleep_quality: number // 1-3
  stress: number // 1-3
  diet_risk: string
  supplements: string // comma-separated supplement IDs
  sick: boolean
  hot_shower: boolean
  notes: string | null
  alcohol_units: number | null
  caffeine_servings: number | null
  symptoms_json: Record<string, number> | null
  photos: Photo[]
  effective_flags: string[]
  photo_derived_flags: string[]
  user_added_flags: string[]
  photo_signal: PhotoSignal
  created_at: string
  updated_at: string
}

export interface EntryCreate {
  date: string
  schema_version?: number
  entry_time?: string
  period_of_day?: string
  overall: number
  bloating: number
  stool_status?: StoolStatus
  bristol_type?: number
  joint_pain: number
  neuro: number
  sleep_quality: number
  stress: number
  diet_risk: string
  supplements: string
  sick: boolean
  hot_shower?: boolean
  notes?: string
  alcohol_units?: number | null
  caffeine_servings?: number | null
  symptoms_json?: Record<string, number>
}

export interface PhotoIngredient {
  id: number
  name: string
  canonical_name: string | null
  visible: boolean
  confidence: number
  user_edited: boolean
  histamine_score: number | null
  fodmap_oligos: string | null
  fodmap_fructose: string | null
  fodmap_polyols: string | null
  fodmap_lactose: string | null
  contains_gluten: boolean | null
  contains_dairy: boolean | null
}

export interface PhotoAnalysis {
  id: number
  photo_id: number
  status: 'pending' | 'analyzing' | 'complete' | 'failed' | 'confirmed'
  dish_name: string | null
  cuisine: string | null
  dish_confidence: number | null
  ingredients: PhotoIngredient[]
  error_message: string | null
  created_at: string
  updated_at: string
}
