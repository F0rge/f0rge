import type { Entry } from './entries'

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
