'use client'

import { useState } from 'react'
import { Download } from 'lucide-react'
import { apiGetRaw, handleMutationError } from '@/lib/api/client'
import { SettingsCard } from './settings-card'

export function ExportDataSection() {
  const [exporting, setExporting] = useState(false)

  const handleExportCsv = async () => {
    setExporting(true)
    try {
      const res = await apiGetRaw('/export/feature-matrix.csv')
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      const disposition = res.headers.get('Content-Disposition')
      const match = disposition?.match(/filename="?([^"]+)"?/)
      a.download = match?.[1] ?? 'feature_matrix.csv'
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
    } catch (err) {
      console.error('CSV export failed:', err)
      handleMutationError(err, 'Export failed')
    } finally {
      setExporting(false)
    }
  }

  return (
    <SettingsCard icon={Download} iconClassName="text-green-500" title="Export Data">
      <p className="text-sm text-muted-foreground">
        Download all check-in and health metric data as a CSV feature matrix for analysis.
      </p>
      <button
        type="button"
        onClick={handleExportCsv}
        disabled={exporting}
        className="flex min-h-[44px] w-full items-center justify-center gap-2 rounded-xl border border-border px-4 py-2.5 text-sm font-medium transition-all hover:bg-muted disabled:opacity-50"
      >
        <Download className={`size-4 ${exporting ? 'animate-pulse' : ''}`} />
        {exporting ? 'Exporting...' : 'Download CSV'}
      </button>
    </SettingsCard>
  )
}
