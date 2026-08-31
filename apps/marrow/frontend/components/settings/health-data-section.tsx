'use client'

import { useMemo, useState, type ChangeEvent } from 'react'
import { toast } from 'sonner'
import { Download, Heart, Upload } from 'lucide-react'
import { formatDisplayDate, formatLocalDate } from '@f0rge/ui'
import { handleMutationError } from '@f0rge/ui/api'
import { useHealthMetricsRange, useImportHealthSamples } from '@/lib/api/hooks'
import { HEALTH_CSV_TEMPLATE, parseHealthImportText } from '@/lib/health-import/parse-health-file'
import { SettingsCard } from './settings-card'
import { BUTTON_CLASS } from './constants'

function lastDaysRange(days: number): { start: string; end: string } {
  const end = new Date()
  const start = new Date()
  start.setDate(end.getDate() - (days - 1))
  return { start: formatLocalDate(start), end: formatLocalDate(end) }
}

export function HealthDataSection() {
  const range = useMemo(() => lastDaysRange(30), [])
  const recent = useHealthMetricsRange(range.start, range.end)
  const importSamples = useImportHealthSamples()
  const [uploading, setUploading] = useState(false)

  const downloadTemplate = () => {
    const blob = new Blob([HEALTH_CSV_TEMPLATE], { type: 'text/csv;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = 'marrow-health-import.csv'
    link.click()
    URL.revokeObjectURL(url)
  }

  const handleFile = async (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setUploading(true)
    try {
      const parsed = parseHealthImportText(await file.text(), file.name)
      if (!parsed.ok) {
        toast.error(parsed.error)
        return
      }
      const samples = parsed.samples.map((sample) => ({ ...sample, source: 'manual_import' }))
      const result = (await importSamples.mutateAsync(samples)) as { dates_upserted: number }
      toast.success(`Imported ${result.dates_upserted} day${result.dates_upserted === 1 ? '' : 's'}`)
    } catch (err) {
      handleMutationError(err, 'Import failed')
    } finally {
      setUploading(false)
      e.target.value = ''
    }
  }

  const rows = recent.data ?? []
  const busy = uploading || importSamples.isPending

  return (
    <SettingsCard icon={Heart} iconClassName="text-muted-foreground" title="Health data">
      <p className="text-sm text-muted-foreground">
        Import daily sleep, HRV, resting heart rate, and steps. Signals uses these values the next
        time it predicts how you will feel. Apple Health on iPhone comes later.
      </p>
      <button type="button" onClick={downloadTemplate} className={BUTTON_CLASS}>
        <Download className="size-4" />
        Download CSV template
      </button>
      <label className={`${BUTTON_CLASS} cursor-pointer ${busy ? 'opacity-50' : ''}`}>
        <Upload className="size-4" />
        {busy ? 'Importing…' : 'Upload CSV or JSON'}
        <input
          type="file"
          accept=".csv,.json,text/csv,application/json"
          onChange={handleFile}
          className="hidden"
          disabled={busy}
        />
      </label>
      {rows.length > 0 ? (
        <div className="space-y-2">
          <p className="text-xs font-medium text-muted-foreground">Last 30 days</p>
          <ul className="max-h-48 space-y-1 overflow-y-auto text-sm">
            {rows.slice(0, 14).map((row) => (
              <li key={row.date} className="flex items-baseline justify-between gap-3">
                <span>{formatDisplayDate(row.date)}</span>
                <span className="text-muted-foreground">
                  {row.sleep_hours != null ? `${row.sleep_hours}h sleep` : '—'}
                  {row.steps != null ? ` · ${row.steps.toLocaleString()} steps` : ''}
                </span>
              </li>
            ))}
          </ul>
        </div>
      ) : (
        <p className="text-xs text-muted-foreground">No imported days yet.</p>
      )}
    </SettingsCard>
  )
}
