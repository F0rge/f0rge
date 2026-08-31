export interface Photo {
  id: number
  entry_id: number
  filename: string | null
  meal_id?: number | null
  label: string | null
  meal_time: string | null
  created_at: string
  source_photo_id?: number | null
  tagged_by_handle?: string | null
  tagged_with_handles?: string[]
  dish_name?: string | null
  hidden_at?: string | null
  diet_tags?: string[]
  derived_diet_tags?: string[]
  has_image?: boolean
  icon_key?: string | null
}

export interface EntryStats {
  total_checkins: number
  current_streak_days: number
  week_days: boolean[] // 7 items, Mon→Sun; true = checked in that day
  week_today_index: number // Mon=0 .. Sun=6, app-timezone today
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

export interface MedicationIntake {
  key: string
  dose?: string
  reason?: string
  time?: string // wall-clock "HH:MM", stamped client-side at log time
}

export interface SymptomEvent {
  key: string
  severity: number
  time?: string // wall-clock "HH:MM", stamped client-side at log time
}

export interface Entry {
  id: number
  date: string // YYYY-MM-DD
  schema_version: number
  entry_time: string | null
  period_of_day: 'morning' | 'midday' | 'evening' | 'night' | null
  overall: number | null // 1-5, or null if not rated
  bloating: number | null // 0-3, or null if not rated
  // v1 legacy
  stool_normal: boolean | null
  stool_type: string | null
  // v2
  stool_status: StoolStatus | null
  bristol_type: number | null // 1-7
  // v4
  stool_completeness: 'complete' | 'incomplete' | null
  joint_pain: number // 0-3
  neuro: number // -1, 0, 1
  sleep_quality: number | null // 1-5, or null if not rated
  stress: number | null // 1-5, or null if not rated
  diet_risk: string
  supplements: string // comma-separated supplement IDs
  sick: boolean
  hot_shower: boolean
  notes: string | null
  alcohol_units: number | null
  caffeine_servings: number | null
  symptoms_json: Record<string, number> | null
  medications: MedicationIntake[]
  symptom_events: SymptomEvent[]
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
  overall?: number | null
  bloating?: number | null
  stool_status?: StoolStatus
  bristol_type?: number
  stool_completeness?: 'complete' | 'incomplete' | null
  joint_pain?: number
  neuro?: number
  sleep_quality?: number | null
  stress?: number | null
  diet_risk: string
  supplements: string
  sick: boolean
  hot_shower?: boolean
  notes?: string
  alcohol_units?: number | null
  caffeine_servings?: number | null
  symptoms_json?: Record<string, number>
  medications?: MedicationIntake[]
  symptom_events?: SymptomEvent[]
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
  status: 'pending' | 'analyzing' | 'complete' | 'needs_review' | 'failed' | 'confirmed'
  dish_name: string | null
  cuisine: string | null
  dish_confidence: number | null
  ingredients: PhotoIngredient[]
  gluten_free_confirmed: boolean
  lactose_free_confirmed: boolean
  error_message: string | null
  created_at: string
  updated_at: string
}

// OpenAPI codegen types live in lib/api/generated/schema.ts — drift-checked in CI.
// Entry hooks still use hand-written types above until nullable/enum gaps are closed.
export type { components } from '../generated/schema'
