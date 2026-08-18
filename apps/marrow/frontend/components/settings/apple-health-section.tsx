'use client'

import { useState } from 'react'
import { toast } from 'sonner'
import { Heart, Upload } from 'lucide-react'
import { apiPostForm, handleMutationError } from '@f0rge/ui/api'
import { SettingsCard } from './settings-card'

export function AppleHealthSection() {
  const [uploading, setUploading] = useState(false)

  const handleXmlUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setUploading(true)
    try {
      const formData = new FormData()
      formData.append('file', file)
      await apiPostForm('/health-metrics/import', formData)
      toast.success('Health data imported')
    } catch (err) {
      handleMutationError(err, 'Import failed')
    } finally {
      setUploading(false)
      e.target.value = ''
    }
  }

  return (
    <SettingsCard icon={Heart} iconClassName="text-muted-foreground" title="Apple Health">
      <p className="text-sm text-muted-foreground">
        Auto-syncs via Health Auto Export iOS app. Use this upload for manual XML imports as a backup.
      </p>
      <label
        className={`flex min-h-[44px] w-full cursor-pointer items-center justify-center gap-2 rounded-xl border border-border px-4 py-2.5 text-sm font-medium transition-all hover:bg-muted ${uploading ? 'opacity-50' : ''}`}
      >
        <Upload className="size-4" />
        {uploading ? 'Importing...' : 'Upload Apple Health XML'}
        <input
          type="file"
          accept=".xml,.json"
          onChange={handleXmlUpload}
          className="hidden"
          disabled={uploading}
        />
      </label>
    </SettingsCard>
  )
}
