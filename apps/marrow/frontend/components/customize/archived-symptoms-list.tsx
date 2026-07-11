'use client'

/**
 * Collapsible archived-symptoms list for /customize/symptoms.
 *
 * Renders nothing when archived.length is 0.
 */

import { useState } from 'react'
import { ChevronDown, Undo2 } from 'lucide-react'
import { Button } from '@f0rge/ui'
import { RowItem } from '@/components/customize/row-item'
import type { SymptomCatalogItem } from '@/lib/api/types'

interface ArchivedSymptomsListProps {
  archived: SymptomCatalogItem[]
  onRestore: (symptom: SymptomCatalogItem) => void
}

export function ArchivedSymptomsList({ archived, onRestore }: ArchivedSymptomsListProps) {
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
          {archived.map((symptom) => (
            <RowItem
              key={symptom.key}
              label={symptom.label}
              actions={
                <Button
                  variant="ghost"
                  size="icon"
                  className="size-8 text-muted-foreground hover:text-foreground"
                  aria-label={`Restore ${symptom.label}`}
                  onClick={() => onRestore(symptom)}
                >
                  <Undo2 className="size-3.5" />
                </Button>
              }
              dimmed
            />
          ))}
        </div>
      )}
    </div>
  )
}
