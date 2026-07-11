'use client'

/**
 * Collapsible archived-trackers list for /customize/trackers.
 *
 * Renders nothing when archived.length is 0.
 */

import { useState } from 'react'
import { ChevronDown, Undo2 } from 'lucide-react'
import { Button } from '@f0rge/ui'
import { RowItem } from '@/components/customize/row-item'
import { ICON_COMPONENT_MAP } from '@/components/checkin/cards/components/IconPicker'
import type { Tracker } from '@/lib/api/types'

interface ArchivedTrackersListProps {
  archived: Tracker[]
  onRestore: (tracker: Tracker) => void
}

export function ArchivedTrackersList({ archived, onRestore }: ArchivedTrackersListProps) {
  const [open, setOpen] = useState(false)
  if (archived.length === 0) return null

  return (
    <div className="mt-6">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between text-xs text-muted-foreground hover:text-foreground transition-colors py-2"
      >
        <span className="font-semibold uppercase tracking-wider">
          Archived ({archived.length})
        </span>
        <ChevronDown className={`size-4 transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>

      {open && (
        <div className="mt-1 rounded-lg border border-border bg-muted/30">
          {archived.map((tracker) => {
            const IconComponent = tracker.icon ? ICON_COMPONENT_MAP[tracker.icon] : null
            return (
              <RowItem
                key={tracker.id}
                icon={
                  IconComponent ? (
                    <IconComponent className="size-4 text-muted-foreground" />
                  ) : undefined
                }
                label={tracker.name}
                meta={
                  <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                    {tracker.kind}
                    {tracker.unit ? ` · ${tracker.unit}` : ''}
                  </span>
                }
                actions={
                  <Button
                    variant="ghost"
                    size="icon"
                    className="size-8 text-muted-foreground hover:text-foreground"
                    aria-label={`Restore ${tracker.name}`}
                    onClick={() => onRestore(tracker)}
                  >
                    <Undo2 className="size-3.5" />
                  </Button>
                }
                dimmed
              />
            )
          })}
        </div>
      )}
    </div>
  )
}
