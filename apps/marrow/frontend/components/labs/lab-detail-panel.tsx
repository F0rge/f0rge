'use client'

import { useState } from 'react'
import { toast } from 'sonner'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@f0rge/ui'
import { useDeleteLab } from '@/lib/api/hooks'
import { handleMutationError } from '@f0rge/ui/api'
import { LabDetailContent } from './lab-detail-content'
import { LabFormDialog } from './lab-form-dialog'
import type { Lab } from '@/lib/api/types'

interface LabDetailPanelProps {
  lab: Lab | null
  open: boolean
  onOpenChange: (open: boolean) => void
}

/** Mobile-only dialog detail view. */
export function LabDetailPanel({ lab, open, onOpenChange }: LabDetailPanelProps) {
  const [editOpen, setEditOpen] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const deleteLab = useDeleteLab()

  if (!lab) return null

  async function handleDelete() {
    if (!confirmDelete) { setConfirmDelete(true); return }
    try {
      await deleteLab.mutateAsync(lab!.id)
      toast.success('Lab deleted')
      onOpenChange(false)
    } catch (err) {
      handleMutationError(err, 'Failed to delete lab')
    }
  }

  return (
    <>
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-2xl">
          <DialogHeader>
            <DialogTitle className="sr-only">{lab.name}</DialogTitle>
          </DialogHeader>
          <LabDetailContent
            lab={lab}
            confirmDelete={confirmDelete}
            deletePending={deleteLab.isPending}
            onDelete={handleDelete}
            onEdit={() => setEditOpen(true)}
          />
        </DialogContent>
      </Dialog>

      <LabFormDialog
        key={`edit-${lab.id}`}
        open={editOpen}
        onOpenChange={(o) => {
          setEditOpen(o)
          if (!o) onOpenChange(false)
        }}
        lab={lab}
      />
    </>
  )
}
