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

/** Mobile-only bottom sheet — same Dialog + className recipe as PhotoFocusOverlay. */
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
      <Dialog
        open={open && !editOpen}
        onOpenChange={(next) => {
          if (editOpen) return
          if (!next) setConfirmDelete(false)
          onOpenChange(next)
        }}
      >
        <DialogContent className="fixed inset-x-0 bottom-0 top-auto m-0 flex max-h-[92vh] w-full max-w-full min-w-0 translate-none flex-col gap-0 overflow-hidden rounded-b-none rounded-t-2xl p-0 duration-200 data-open:slide-in-from-bottom data-closed:slide-out-to-bottom">
          <div className="flex h-10 shrink-0 items-end justify-center pb-1">
            <div className="h-1 w-10 rounded-full bg-border" aria-hidden />
          </div>
          <DialogHeader className="sr-only">
            <DialogTitle>{lab.name}</DialogTitle>
          </DialogHeader>
          <div className="min-h-0 min-w-0 flex-1 overflow-x-hidden overflow-y-auto px-4 pb-[max(1rem,env(safe-area-inset-bottom))]">
            <LabDetailContent
              lab={lab}
              confirmDelete={confirmDelete}
              deletePending={deleteLab.isPending}
              onDelete={handleDelete}
              onEdit={() => setEditOpen(true)}
            />
          </div>
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
