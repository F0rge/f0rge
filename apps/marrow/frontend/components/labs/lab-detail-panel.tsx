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

/** Mobile-only near-full-screen sheet (same Dialog primitive as photo-focus overlay). */
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
        open={open}
        onOpenChange={(next) => {
          if (!next) setConfirmDelete(false)
          onOpenChange(next)
        }}
      >
        <DialogContent
          showCloseButton={false}
          style={{
            top: 'max(0.5rem, env(safe-area-inset-top, 0px))',
            right: 0,
            bottom: 0,
            left: 0,
            width: '100%',
            maxWidth: 'none',
            height: 'auto',
            maxHeight: 'none',
            translate: 'none',
            transform: 'none',
            animation: 'none',
            zIndex: 60,
          }}
          className="fixed z-[60] m-0 flex w-full max-w-none min-w-0 flex-col gap-0 overflow-hidden rounded-b-none rounded-t-2xl p-0 sm:max-w-none"
        >
          <div className="relative flex shrink-0 items-center justify-center pt-2">
            <div className="h-1 w-10 rounded-full bg-border" aria-hidden />
            <DialogClose
              render={
                <Button
                  variant="ghost"
                  size="icon"
                  className="absolute top-0.5 right-1 size-11"
                />
              }
            >
              <X className="size-5" />
              <span className="sr-only">Close</span>
            </DialogClose>
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
