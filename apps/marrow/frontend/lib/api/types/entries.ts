import type { components } from '../generated/schema'

/** OpenAPI-backed entry types (codegen from backend schema). */
export type Entry = components['schemas']['EntryResponse']
export type EntryCreate = components['schemas']['EntryCreate']
export type EntryStats = components['schemas']['EntryStatsResponse']

export type Photo = components['schemas']['PhotoResponse']

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
  time?: string
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
