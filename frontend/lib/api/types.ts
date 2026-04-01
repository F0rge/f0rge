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
  stool_type: string | null
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
  stool_type?: string
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
