'use client'

import { useState } from 'react'
import { toast } from 'sonner'
import { X } from 'lucide-react'
import { useDeleteLab } from '@/lib/api/hooks'
import { handleMutationError } from '@/lib/api/client'
import { LabDetailContent } from './lab-detail-content'
import { LabFormDialog } from './lab-form-dialog'
import type { Lab } from '@/lib/api/types'

interface LabDetailInlineProps {
  lab: Lab
  onClose: () => void
}

/** Desktop inline detail panel (lg+). */
export function LabDetailInline({ lab, onClose }: LabDetailInlineProps) {
  const [editOpen, setEditOpen] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const deleteLab = useDeleteLab()

  async function handleDelete() {
    if (!confirmDelete) { setConfirmDelete(true); return }
    try {
      await deleteLab.mutateAsync(lab.id)
      toast.success('Lab deleted')
      onClose()
    } catch (err) {
      handleMutationError(err, 'Failed to delete lab')
    }
  }

  return (
    <>
      <div className="relative sticky top-4 rounded-xl border border-border bg-card p-4 space-y-4 max-h-[calc(100vh-120px)] overflow-y-auto">
        <button
          type="button"
          onClick={onClose}
          className="absolute right-3 top-3 flex size-8 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
          aria-label="Close detail panel"
        >
          <X className="size-4" />
        </button>
        <LabDetailContent
          lab={lab}
          confirmDelete={confirmDelete}
          deletePending={deleteLab.isPending}
          onDelete={handleDelete}
          onEdit={() => setEditOpen(true)}
        />
      </div>

      <LabFormDialog
        key={`edit-${lab.id}`}
        open={editOpen}
        onOpenChange={setEditOpen}
        lab={lab}
      />
    </>
  )
}
