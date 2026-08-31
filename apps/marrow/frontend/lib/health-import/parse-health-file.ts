export const HEALTH_CSV_TEMPLATE = `date,sleep_hours,hrv_mean,resting_hr,steps,spo2,active_minutes,wrist_temp_deviation
2026-08-01,7.5,45,62,8432,97.2,420,
2026-08-02,6.2,38,68,5120,96.8,280,
`

const FLOAT_FIELDS = [
  'hrv_mean',
  'hrv_std',
  'resting_hr',
  'sleep_hours',
  'sleep_deep_min',
  'sleep_rem_min',
  'sleep_core_min',
  'sleep_awake_min',
  'sleep_deep_pct',
  'sleep_rem_pct',
  'sleep_efficiency',
  'active_minutes',
  'spo2',
  'wrist_temp_deviation',
] as const

const INT_FIELDS = ['steps'] as const
const STRING_FIELDS = ['sleep_start', 'sleep_end'] as const

export type HealthMetricSample = {
  date: string
  source?: string
  hrv_mean?: number
  hrv_std?: number
  resting_hr?: number
  sleep_hours?: number
  sleep_deep_min?: number
  sleep_rem_min?: number
  sleep_core_min?: number
  sleep_awake_min?: number
  sleep_deep_pct?: number
  sleep_rem_pct?: number
  sleep_efficiency?: number
  sleep_start?: string
  sleep_end?: string
  steps?: number
  active_minutes?: number
  spo2?: number
  wrist_temp_deviation?: number
}

export type ParseHealthFileResult =
  | { ok: true; samples: HealthMetricSample[] }
  | { ok: false; error: string }

const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/

export function parseHealthImportText(text: string, filename = ''): ParseHealthFileResult {
  const trimmed = text.replace(/^\uFEFF/, '').trim()
  if (!trimmed) return { ok: false, error: 'File is empty.' }

  const looksJson = trimmed.startsWith('{') || trimmed.startsWith('[') || filename.endsWith('.json')
  if (looksJson) return parseJson(trimmed)
  return parseCsv(trimmed)
}

function parseJson(text: string): ParseHealthFileResult {
  let parsed: unknown
  try {
    parsed = JSON.parse(text)
  } catch {
    return { ok: false, error: 'Could not parse JSON.' }
  }

  if (isAutoExport(parsed)) {
    return {
      ok: false,
      error: 'Health Auto Export files are no longer imported here. Use the CSV template or a JSON array of daily rows.',
    }
  }

  const rows = Array.isArray(parsed)
    ? parsed
    : isRecord(parsed) && Array.isArray(parsed.samples)
      ? parsed.samples
      : null
  if (rows == null) {
    return { ok: false, error: 'JSON must be an array of daily rows, or { "samples": [...] }.' }
  }

  const samples: HealthMetricSample[] = []
  for (const [index, row] of rows.entries()) {
    const sample = normalizeRow(row)
    if (sample == null) {
      return { ok: false, error: `Row ${index + 1} is missing a valid date (YYYY-MM-DD).` }
    }
    if (!hasMetrics(sample)) {
      return {
        ok: false,
        error: `Row ${index + 1} has a date but no recognized metrics. Use headers like sleep_hours, hrv_mean, or steps.`,
      }
    }
    samples.push(sample)
  }
  return finish(samples)
}

function parseCsv(text: string): ParseHealthFileResult {
  const lines = text.split(/\r?\n/).map((line) => line.trim()).filter(Boolean)
  if (lines.length < 2) return { ok: false, error: 'CSV needs a header row and at least one data row.' }

  const headers = lines[0].split(',').map((h) => normalizeHeader(h))
  const dateIdx = headers.indexOf('date')
  if (dateIdx < 0) return { ok: false, error: 'CSV must include a date column.' }

  const samples: HealthMetricSample[] = []
  for (let i = 1; i < lines.length; i += 1) {
    const cols = lines[i].split(',').map((c) => c.trim())
    const raw: Record<string, string> = {}
    headers.forEach((header, idx) => {
      raw[header] = cols[idx] ?? ''
    })
    const sample = normalizeRow(raw)
    if (sample == null) {
      return { ok: false, error: `Row ${i + 1} is missing a valid date (YYYY-MM-DD).` }
    }
    if (!hasMetrics(sample)) {
      return {
        ok: false,
        error: `Row ${i + 1} has a date but no recognized metrics. Use headers like sleep_hours, hrv_mean, or steps.`,
      }
    }
    samples.push(sample)
  }
  return finish(samples)
}

function finish(samples: HealthMetricSample[]): ParseHealthFileResult {
  if (samples.length === 0) return { ok: false, error: 'No daily rows found.' }
  return { ok: true, samples }
}

function normalizeRow(row: unknown): HealthMetricSample | null {
  if (!isRecord(row)) return null
  const dateRaw = String(row.date ?? '').slice(0, 10)
  if (!ISO_DATE.test(dateRaw)) return null

  const sample: HealthMetricSample = { date: dateRaw }
  for (const key of FLOAT_FIELDS) {
    const value = parseNumber(row[key])
    if (value != null) sample[key] = value
  }
  for (const key of INT_FIELDS) {
    const value = parseNumber(row[key])
    if (value != null) sample[key] = Math.round(value)
  }
  for (const key of STRING_FIELDS) {
    const value = row[key]
    if (typeof value === 'string' && value.trim()) sample[key] = value.trim()
  }
  return sample
}

function hasMetrics(sample: HealthMetricSample): boolean {
  return Object.keys(sample).some((key) => key !== 'date' && key !== 'source')
}

function normalizeHeader(header: string): string {
  return header.trim().toLowerCase().replace(/[\s-]+/g, '_')
}

function parseNumber(value: unknown): number | null {
  if (value == null || value === '') return null
  const n = typeof value === 'number' ? value : Number(String(value).trim())
  return Number.isFinite(n) ? n : null
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function isAutoExport(value: unknown): boolean {
  return isRecord(value) && isRecord(value.data) && Array.isArray(value.data.metrics)
}
