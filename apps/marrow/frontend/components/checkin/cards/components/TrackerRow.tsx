'use client'

import { Stepper } from '@f0rge/ui'
import { Archive, Circle } from 'lucide-react'
import { ICON_COMPONENT_MAP } from './IconPicker'
import type { Tracker } from '@/lib/api/types'

interface TrackerRowProps {
  tracker: Tracker
  value: number
  onChange: (v: number) => void
  onArchive?: () => void
  /** When true, renders the row as archived (muted, line-through, Restore button) */
  archived?: boolean
  onRestore?: () => void
}

function TrackerIcon({ icon }: { icon: string | null }) {
  if (!icon) {
    return (
      <div className="size-9 rounded-lg bg-muted flex items-center justify-center shrink-0">
        <Circle className="size-5 text-muted-foreground" />
      </div>
    )
  }

  const LucideComp = ICON_COMPONENT_MAP[icon.toLowerCase()]
  if (LucideComp) {
    return (
      <div className="size-9 rounded-lg bg-muted flex items-center justify-center shrink-0">
        <LucideComp className="size-5 text-foreground" />
      </div>
    )
  }

  // Fallback: emoji / freeform text — still in a tile
  return (
    <div className="size-9 rounded-lg bg-muted flex items-center justify-center shrink-0">
      <span className="text-base leading-none" aria-hidden="true">
        {icon}
      </span>
    </div>
  )
}

// Compact inline Yes/No control
function CompactBinary({
  value,
  onChange,
  label,
}: {
  value: boolean
  onChange: (v: boolean) => void
  label: string
}) {
  return (
    <div className="flex items-center rounded-md border border-border overflow-hidden shrink-0">
      <button
        type="button"
        onClick={() => onChange(true)}
        aria-pressed={value}
        aria-label={`${label}: Yes`}
        className={`px-3 py-1.5 text-xs font-medium transition-colors ${
          value ? 'bg-primary text-primary-foreground' : 'hover:bg-muted'
        }`}
      >
        Yes
      </button>
      <div className="w-px h-5 bg-border" aria-hidden="true" />
      <button
        type="button"
        onClick={() => onChange(false)}
        aria-pressed={!value}
        aria-label={`${label}: No`}
        className={`px-3 py-1.5 text-xs font-medium transition-colors ${
          !value ? 'bg-primary text-primary-foreground' : 'hover:bg-muted'
        }`}
      >
        No
      </button>
    </div>
  )
}

export function TrackerRow({
  tracker,
  value,
  onChange,
  onArchive,
  archived = false,
  onRestore,
}: TrackerRowProps) {
  if (archived) {
    return (
      <li className="flex items-center gap-3 px-4 py-2.5 opacity-60">
        <TrackerIcon icon={tracker.icon} />
        <div className="flex-1 min-w-0">
          <div className="text-sm font-medium leading-tight text-muted-foreground line-through">
            {tracker.name}
          </div>
          {tracker.unit && (
            <div className="text-xs text-muted-foreground">{tracker.unit}</div>
          )}
        </div>
        {onRestore && (
          <button
            type="button"
            onClick={onRestore}
            className="text-xs font-medium text-foreground hover:underline shrink-0"
          >
            Restore
          </button>
        )}
      </li>
    )
  }

  return (
    <li className="group flex items-center gap-3 px-4 py-3">
      <TrackerIcon icon={tracker.icon} />
      <div className="flex-1 min-w-0">
        <div className="text-sm font-medium leading-tight">{tracker.name}</div>
        {tracker.unit && (
          <div className="text-xs text-muted-foreground">{tracker.unit}</div>
        )}
      </div>

      {tracker.kind === 'binary' ? (
        <CompactBinary
          value={value === 1}
          onChange={(v) => onChange(v ? 1 : 0)}
          label={tracker.name}
        />
      ) : (
        <Stepper
          size="compact"
          min={0}
          max={99}
          value={value}
          onChange={onChange}
          label={tracker.name}
        />
      )}

      {onArchive && (
        <button
          type="button"
          onClick={onArchive}
          aria-label={`Archive ${tracker.name}`}
          className="shrink-0 rounded p-1 text-muted-foreground/60 transition-opacity
            opacity-100 lg:opacity-0 lg:group-hover:opacity-100 focus-visible:opacity-100
            hover:text-destructive"
        >
          <Archive className="size-4" />
        </button>
      )}
    </li>
  )
}
