export type LabType =
  | 'blood'
  | 'breath'
  | 'imaging'
  | 'microbiology'
  | 'allergy'
  | 'comprehensive'
  | 'other'

export type MarkerFlag = 'low' | 'normal' | 'high' | 'abnormal' | 'unknown'

export type SourceKind = 'text' | 'pdf' | 'image' | 'vault_markdown'

export type ReviewStatus = 'confirmed' | 'needs_review'

export interface LabMarker {
  id: number
  catalog_id: number
  canonical_name: string
  display_name: string
  value: number | null
  value_text: string | null
  unit: string | null
  ref_low: number | null
  ref_high: number | null
  ref_text: string | null
  flag: MarkerFlag
}

export interface Lab {
  id: number
  lab_date: string // YYYY-MM-DD
  name: string
  type: LabType
  lab_location: string | null
  source_kind: SourceKind
  source_path: string | null
  attachment_path: string | null
  extraction_model: string | null
  extraction_confidence: number | null
  review_status: ReviewStatus
  notes: string | null
  created_at: string
  updated_at: string
  markers: LabMarker[]
}

export interface LabMarkerCreate {
  catalog_id: number
  canonical_name: string
  display_name: string
  value?: number | null
  value_text?: string | null
  unit?: string | null
  ref_low?: number | null
  ref_high?: number | null
  ref_text?: string | null
}

export interface LabCreate {
  lab_date: string
  name: string
  type: LabType
  lab_location?: string | null
  source_kind?: SourceKind
  source_path?: string | null
  notes?: string | null
  markers: LabMarkerCreate[]
}

export interface LabUpdate {
  lab_date?: string
  name?: string
  type?: LabType
  lab_location?: string | null
  notes?: string | null
  markers?: LabMarkerCreate[]
}

export interface LabMarkerCatalog {
  id: number
  canonical_name: string
  display_name: string
  common_units: string[]
  description: string | null
  created_at: string
}

export interface LabMarkerAlias {
  id: number
  catalog_id: number
  alias: string
  language: string | null
}

export interface MarkerHistoryPoint {
  lab_date: string
  value: number | null
  value_text: string | null
  unit: string | null
  ref_low: number | null
  ref_high: number | null
  flag: MarkerFlag
}

export interface ExtractedLab {
  lab_date: string
  name: string
  type: LabType
  lab_location: string | null
  notes: string | null
}

export interface ExtractedMarker {
  canonical_match: string | null
  proposed_canonical: string | null
  display_name: string
  value: number | null
  value_text: string | null
  unit: string | null
  ref_low: number | null
  ref_high: number | null
  ref_text: string | null
}

export interface ExtractedLabPayload {
  lab: ExtractedLab
  markers: ExtractedMarker[]
  confidence: number
}

export interface ExtractionResult {
  payload: ExtractedLabPayload
  raw_response: string
  model: string
  attempts: number
  retried_due_to: string[]
}
