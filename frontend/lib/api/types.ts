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

export interface SupplementCatalogItem {
  id: number
  key: string
  label: string
  archived: boolean
  first_used_at: string | null
  last_used_at: string | null
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

export interface AuthUser {
  authenticated: boolean
}

export interface WeatherDailySummary {
  date: string
  pressure_mean: number
  pressure_min: number
  pressure_max: number
  pressure_delta_24h: number | null
  temp_mean: number
  temp_min: number
  temp_max: number
  humidity_mean: number
  reading_count: number
}

export interface HealthMetricResponse {
  id: number
  date: string
  hrv_mean: number | null
  hrv_std: number | null
  resting_hr: number | null
  sleep_hours: number | null
  sleep_deep_pct: number | null
  sleep_rem_pct: number | null
  steps: number | null
  active_minutes: number | null
  spo2: number | null
  wrist_temp_deviation: number | null
  source: string
  created_at: string
  updated_at: string
}

export interface EnrichedDayResponse {
  entry: Entry | null
  weather: WeatherDailySummary | null
  health_metrics: HealthMetricResponse | null
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

// ── Insights types ─────────────────────────────────────────────────────────────

export interface TrendPoint {
  date: string
  value: number | null
  rolling_avg_7: number | null
}

export interface TrendSeries {
  key: string
  label: string
  category: string
  points: TrendPoint[]
  current: number | null
  rolling_avg_7: number | null
  delta_30d: number | null
}

export interface TrendsResponse {
  series: TrendSeries[]
}

export interface CorrelateRow {
  feature: string
  label: string
  category: string
  rho: number
  n: number
  best_lag: number
}

export interface CorrelatesResponse {
  outcome: string
  positive: CorrelateRow[]
  negative: CorrelateRow[]
}

export interface TreatmentResponseRow {
  treatment_id: number
  name: string
  type: string
  start_date: string
  end_date: string | null
  baseline_mean: number | null
  during_mean: number | null
  after_mean: number | null
  baseline_n: number
  during_n: number
  after_n: number
  delta_during_vs_baseline: number | null
}

export interface TreatmentResponseList {
  outcome: string
  rows: TreatmentResponseRow[]
}

export interface SleepNextDayPoint {
  date: string
  sleep_value: number
  next_day_outcome: number
}

export interface SleepNextDayResponse {
  outcome: string
  metric: string
  points: SleepNextDayPoint[]
  rho: number | null
  n: number
}

// ── Labs types ─────────────────────────────────────────────────────────────────

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

// ── Tracker types ──────────────────────────────────────────────────────────────

export type TrackerKind = 'counter' | 'binary'

export interface Tracker {
  id: number
  name: string
  kind: TrackerKind
  icon: string | null
  unit: string | null
  position: number
  archived: boolean
  is_seed: boolean
  created_at: string
}

export interface TrackerValue {
  tracker_id: number
  date: string
  value: number
  updated_at: string
}

export interface TrackerCreate {
  name: string
  kind: TrackerKind
  icon?: string | null
  unit?: string | null
  position?: number
}

export interface TrackerUpdate {
  name?: string
  icon?: string | null
  unit?: string | null
  position?: number
  archived?: boolean
}

// ── AI / Settings types ────────────────────────────────────────────────────────

export interface UserSettings {
  llm_provider: string
  llm_model: string | null
  has_llm_api_key: boolean
  embedding_provider: string
  embedding_model: string | null
  has_embedding_api_key: boolean
  has_external_api_token: boolean
}

export interface LLMSettingsUpdate {
  llm_provider?: string
  llm_api_key?: string
  llm_model?: string
}

export interface EmbeddingSettingsUpdate {
  embedding_provider?: string
  embedding_api_key?: string
  embedding_model?: string
}

export interface TestConnectionResponse {
  ok: boolean
  detail?: string | null
}

export interface ExternalTokenResponse {
  token: string // Plaintext bearer token. Exposed exactly once.
}
