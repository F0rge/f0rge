export interface CatalogSuggestionItem {
  key: string
  label: string
}

export interface TrackerSuggestionItem {
  name: string
  kind: string
  icon?: string | null
  unit?: string | null
}

export interface CatalogSuggestions {
  symptoms: CatalogSuggestionItem[]
  medications: CatalogSuggestionItem[]
  supplements: CatalogSuggestionItem[]
  trackers: TrackerSuggestionItem[]
  bulk_supplements: CatalogSuggestionItem[]
  bulk_medications: CatalogSuggestionItem[]
}

export interface CatalogSetupRequest {
  symptoms: string[]
  medications: string[]
  supplements: string[]
  trackers: string[]
}

export interface CatalogSetupResponse {
  symptoms_created: number
  medications_created: number
  supplements_created: number
  trackers_created: number
}
