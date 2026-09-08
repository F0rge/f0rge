'use client'

import { useState } from 'react'
import { toast } from 'sonner'
import { X } from 'lucide-react'
import {
  Button,
  Dialog,
  DialogClose,
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

/** Mobile-only bottom sheet — PhotoFocusOverlay geometry; in-flow close row. */
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
        <DialogContent
          showCloseButton={false}
          className="fixed inset-x-0 bottom-0 top-auto m-0 flex max-h-[92vh] w-full max-w-full min-w-0 translate-none flex-col gap-0 overflow-hidden rounded-b-none rounded-t-2xl p-0 duration-200 data-open:slide-in-from-bottom data-closed:slide-out-to-bottom"
        >
          <div className="shrink-0 pt-[max(0.5rem,env(safe-area-inset-top))]">
            <div className="grid h-11 grid-cols-[2.75rem_1fr_2.75rem] items-center px-1">
              <span aria-hidden />
              <div className="flex justify-center">
                <div className="h-1 w-10 rounded-full bg-border" aria-hidden />
              </div>
              <DialogClose
                render={
                  <Button
                    variant="ghost"
                    size="icon"
                    className="size-11 min-h-[44px] min-w-[44px]"
                  />
                }
              >
                <X className="size-5" />
                <span className="sr-only">Close</span>
              </DialogClose>
            </div>
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
        onOpenChange={setEditOpen}
        lab={lab}
      />
    </>
  )
}
