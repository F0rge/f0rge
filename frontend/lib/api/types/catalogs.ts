export interface SupplementCatalogItem {
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
