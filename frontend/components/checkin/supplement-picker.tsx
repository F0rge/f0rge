'use client'

import { Loader2 } from 'lucide-react'
import { useSupplementCatalog } from '@/lib/api/hooks'

interface SupplementPickerProps {
  value: string // comma-separated supplement keys
  onChange: (value: string) => void
}

export function SupplementPicker({ value, onChange }: SupplementPickerProps) {
  const { data: catalog = [], isLoading } = useSupplementCatalog(false)

  const selectedKeys = new Set(
    value.split(',').map((s) => s.trim()).filter(Boolean),
  )

  const toggle = (key: string) => {
    const current = value.split(',').map((s) => s.trim()).filter(Boolean)
    const next = current.includes(key)
      ? current.filter((s) => s !== key)
      : [...current, key]
    onChange(next.join(','))
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <label className="text-sm font-semibold">Supplements taken</label>
        <div className="flex gap-3 text-xs">
          <button
            type="button"
            onClick={() => onChange(catalog.map((s) => s.key).join(','))}
            className="text-muted-foreground underline"
          >
            All
          </button>
          <button
            type="button"
            onClick={() => onChange('')}
            className="text-muted-foreground underline"
          >
            None
          </button>
        </div>
      </div>

      {isLoading && (
        <div className="flex items-center justify-center py-4 text-muted-foreground">
          <Loader2 className="size-4 animate-spin" />
        </div>
      )}

      {!isLoading && (
        <div className="grid grid-cols-3 gap-2">
          {catalog.map((supp) => {
            const taken = selectedKeys.has(supp.key)
            return (
              <button
                key={supp.key}
                type="button"
                onClick={() => toggle(supp.key)}
                className={[
                  'min-h-[48px] w-full rounded-xl border px-2 py-2.5 text-sm font-medium transition-all',
                  taken
                    ? 'border-primary bg-primary text-primary-foreground shadow-sm'
                    : 'border-border bg-background text-muted-foreground',
                ].join(' ')}
              >
                {supp.label}
              </button>
            )
          })}
        </div>
      )}
    </div>
  )
}
