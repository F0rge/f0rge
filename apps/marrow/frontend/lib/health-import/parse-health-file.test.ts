import { describe, expect, it } from 'vitest'
import { parseHealthImportText } from './parse-health-file'

describe('parseHealthImportText', () => {
  it('parses a CSV with sleep and HRV', () => {
    const csv = `date,sleep_hours,hrv_mean,steps
2026-08-01,7.5,45,8000
2026-08-02,6.0,38,1200
`
    const result = parseHealthImportText(csv, 'health.csv')
    expect(result.ok).toBe(true)
    if (!result.ok) return
    expect(result.samples).toEqual([
      { date: '2026-08-01', sleep_hours: 7.5, hrv_mean: 45, steps: 8000 },
      { date: '2026-08-02', sleep_hours: 6, hrv_mean: 38, steps: 1200 },
    ])
  })

  it('parses a JSON samples array', () => {
    const result = parseHealthImportText(
      JSON.stringify({ samples: [{ date: '2026-08-03', resting_hr: 58 }] }),
      'health.json',
    )
    expect(result.ok).toBe(true)
    if (!result.ok) return
    expect(result.samples[0]).toEqual({ date: '2026-08-03', resting_hr: 58 })
  })

  it('rejects Health Auto Export JSON', () => {
    const result = parseHealthImportText(
      JSON.stringify({ data: { metrics: [{ name: 'Step Count', data: [] }] } }),
      'export.json',
    )
    expect(result.ok).toBe(false)
    if (result.ok) return
    expect(result.error).toMatch(/Auto Export/i)
  })

  it('rejects a missing date column', () => {
    const result = parseHealthImportText('sleep_hours\n7.5\n', 'bad.csv')
    expect(result.ok).toBe(false)
  })

  it('rejects date-only rows with no metric values', () => {
    const result = parseHealthImportText('date\n2026-08-01\n', 'empty.csv')
    expect(result.ok).toBe(false)
    if (result.ok) return
    expect(result.error).toMatch(/recognized metric/i)
  })

  it('rejects unrecognized metric headers', () => {
    const result = parseHealthImportText(
      'date,calories\n2026-08-01,2100\n',
      'unknown.csv',
    )
    expect(result.ok).toBe(false)
    if (result.ok) return
    expect(result.error).toMatch(/recognized metric/i)
  })

  it('accepts spaced headers like Sleep Hours', () => {
    const result = parseHealthImportText('Date,Sleep Hours\n2026-08-04,7.25\n', 'pretty.csv')
    expect(result.ok).toBe(true)
    if (!result.ok) return
    expect(result.samples[0]).toEqual({ date: '2026-08-04', sleep_hours: 7.25 })
  })

  it('skips empty-metric rows when others have values', () => {
    const csv = `date,sleep_hours
2026-08-01,
2026-08-02,7.5
`
    const result = parseHealthImportText(csv, 'mixed.csv')
    expect(result.ok).toBe(true)
    if (!result.ok) return
    expect(result.samples).toEqual([{ date: '2026-08-02', sleep_hours: 7.5 }])
  })
})
