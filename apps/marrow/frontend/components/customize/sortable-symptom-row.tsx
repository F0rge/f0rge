'use client'

/**
 * Sortable row for the /customize/symptoms drag-reorder list.
 * Parent wraps rows in `<Sortable>` from `@f0rge/ui`.
 */

import { GripVertical, Pencil, Trash2 } from 'lucide-react'
import { Button, SortableItem, SortableItemHandle } from '@f0rge/ui'
import { RowItem } from '@/components/customize/row-item'
import type { SymptomCatalogItem } from '@/lib/api/types'

interface SortableSymptomRowProps {
  symptom: SymptomCatalogItem
  onEdit: (symptom: SymptomCatalogItem) => void
  onArchive: (symptom: SymptomCatalogItem) => void
  overlay?: boolean
}

export function SortableSymptomRow({ symptom, onEdit, onArchive, overlay = false }: SortableSymptomRowProps) {
  const dragHandle = overlay ? (
    <span className="text-muted-foreground/40">
      <GripVertical className="size-4" />
    </span>
  ) : (
    <SortableItemHandle
      render={
        <button
          type="button"
          aria-label="Drag to reorder"
          className="touch-none text-muted-foreground/40 hover:text-muted-foreground"
        />
      }
    >
      <GripVertical className="size-4" />
    </SortableItemHandle>
  )

  const row = (
    <RowItem
      dragHandle={dragHandle}
      label={symptom.label}
      actions={
        overlay
          ? undefined
          : (
            <>
              <Button
                variant="ghost"
                size="icon"
                className="size-8 text-muted-foreground hover:text-foreground"
                aria-label={`Edit ${symptom.label}`}
                onClick={() => onEdit(symptom)}
              >
                <Pencil className="size-3.5" />
              </Button>
              <Button
                variant="ghost"
                size="icon"
                className="size-8 text-muted-foreground hover:text-destructive"
                aria-label={`Archive ${symptom.label}`}
                onClick={() => onArchive(symptom)}
              >
                <Trash2 className="size-3.5" />
              </Button>
            </>
          )
      }
      className={overlay ? 'rounded-lg border border-border bg-card shadow-md' : undefined}
    />
  )

  if (overlay) return row

  return (
    <SortableItem value={symptom.key} className="border-b border-border last:border-b-0">
      {row}
    </SortableItem>
  )
}
