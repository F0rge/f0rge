export interface SupplementCatalogItem {
  id: number
  key: string
  label: string
  archived: boolean
  first_used_at: string | null
  last_used_at: string | null
  sort_order: number
}

export interface MedicationCatalogItem {
  id: number
  key: string
  label: string
  archived: boolean
  first_used_at: string | null
  last_used_at: string | null
  sort_order: number
}

export interface DietTagCatalogItem {
  id: number
  key: string
  label: string
  archived: boolean
  sort_order: number
}

export interface SymptomCatalogItem {
  id: number
  key: string
  label: string
  archived: boolean
  first_used_at: string | null
  last_used_at: string | null
  sort_order: number
}

export type FodmapLevel = 'low' | 'moderate' | 'high'

export interface IngredientAlias {
  id: number
  alias: string
  canonical_name: string
  language: string
}

export interface DietaryIngredient {
  id: number
  canonical_name: string
  category: string | null
  histamine_score: number | null
  fodmap_oligos: FodmapLevel | null
  fodmap_fructose: FodmapLevel | null
  fodmap_polyols: FodmapLevel | null
  fodmap_lactose: FodmapLevel | null
  contains_gluten: boolean
  contains_dairy: boolean
  source: string | null
  source_version: string | null
  archived: boolean
  created_at: string
  updated_at: string
  aliases: IngredientAlias[]
}

/** POST body — canonical_name is required and only settable at creation. */
export interface IngredientCreatePayload {
  canonical_name: string
  category: string | null
  histamine_score: number | null
  fodmap_oligos: FodmapLevel | null
  fodmap_fructose: FodmapLevel | null
  fodmap_polyols: FodmapLevel | null
  fodmap_lactose: FodmapLevel | null
  contains_gluten: boolean
  contains_dairy: boolean
}

/** PATCH body — canonical_name is intentionally excluded (rename would orphan aliases). */
export type IngredientUpdatePayload = Partial<Omit<IngredientCreatePayload, 'canonical_name'>> & {
  archived?: boolean
}
