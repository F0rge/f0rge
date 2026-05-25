'use client'

/**
 * Sortable row + ghost row for the /customize/symptoms drag-reorder list.
 *
 * Split out of symptoms-client.tsx to keep that file focused on page-level
 * state. Both helpers are dnd-kit specific: SortableSymptomRow wires the
 * useSortable hook + drag handle; GhostRow renders inside <DragOverlay> with
 * no listeners (the overlay's parent <div style={{ width }}> sizes it).
 *
 * Symptoms have no icon or kind/unit meta — label only.
 */

import { useSortable } from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import { GripVertical, Pencil, Trash2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { RowItem } from '@/components/customize/row-item'
import type { SymptomCatalogItem } from '@/lib/api/types'

interface SortableSymptomRowProps {
  symptom: SymptomCatalogItem
  onEdit: (symptom: SymptomCatalogItem) => void
  onArchive: (symptom: SymptomCatalogItem) => void
}

export function SortableSymptomRow({ symptom, onEdit, onArchive }: SortableSymptomRowProps) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id: symptom.key,
  })

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
  }

  return (
    <div ref={setNodeRef} style={style} className={isDragging ? 'opacity-30' : undefined}>
      <RowItem
        dragHandle={
          <button
            type="button"
            aria-label="Drag to reorder"
            className="touch-none cursor-grab active:cursor-grabbing text-muted-foreground/40 hover:text-muted-foreground"
            {...listeners}
            {...attributes}
          >
            <GripVertical className="size-4" />
          </button>
        }
        label={symptom.label}
        actions={
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
        }
      />
    </div>
  )
}

interface GhostRowProps {
  symptom: SymptomCatalogItem
}

export function GhostRow({ symptom }: GhostRowProps) {
  return (
    <RowItem
      dragHandle={
        <span className="text-muted-foreground/40">
          <GripVertical className="size-4" />
        </span>
      }
      label={symptom.label}
      className="rounded-lg border border-border bg-card shadow-md"
    />
  )
}
