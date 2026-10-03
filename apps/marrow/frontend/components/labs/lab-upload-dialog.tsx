'use client'

import { useState } from 'react'
import { toast } from 'sonner'
import { Upload, Loader2, FileText } from 'lucide-react'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  Button,
  cn,
  Field,
  FieldDescription,
  FieldLabel,
  useFileUpload,
} from '@f0rge/ui'
import { useExtractLabUpload, useImportLabUpload } from '@/lib/api/hooks'
import { handleMutationError } from '@f0rge/ui/api'
import { LabFormDialog } from './lab-form-dialog'
import type { ExtractionResult } from '@/lib/api/types'
import { statusText } from '@/lib/ui/status'

interface LabUploadDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
}

type Phase = 'pick' | 'extracting' | 'review' | 'done'

const ACCEPT = '.pdf,image/jpeg,image/png,image/webp'

export function LabUploadDialog({ open, onOpenChange }: LabUploadDialogProps) {
  const [phase, setPhase] = useState<Phase>('pick')
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [result, setResult] = useState<ExtractionResult | null>(null)
  const [confirmOpen, setConfirmOpen] = useState(false)

  const extractUpload = useExtractLabUpload()
  const importUpload = useImportLabUpload()

  const [{ isDragging, errors }, fileActions] = useFileUpload({
    accept: ACCEPT,
    multiple: false,
    onFilesAdded: (added) => {
      const file = added[0]?.file
      if (file instanceof File) processFile(file)
    },
  })

  function reset() {
    setPhase('pick')
    setSelectedFile(null)
    setResult(null)
    setConfirmOpen(false)
    fileActions.clearFiles()
  }

  function handleClose(o: boolean) {
    if (!o) reset()
    onOpenChange(o)
  }

  async function processFile(file: File) {
    setSelectedFile(file)
    setPhase('extracting')
    try {
      const res = await extractUpload.mutateAsync(file)
      setResult(res)
      setPhase('review')
      setConfirmOpen(true)
    } catch (err) {
      handleMutationError(err, 'Extraction failed')
      setPhase('pick')
      setSelectedFile(null)
    }
  }

  async function handleDirectImport() {
    if (!selectedFile) return
    try {
      await importUpload.mutateAsync({ file: selectedFile })
      toast.success('Lab imported')
      handleClose(false)
    } catch (err) {
      handleMutationError(err, 'Import failed')
    }
  }

  return (
    <>
      <Dialog open={open && !confirmOpen} onOpenChange={handleClose}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Upload Lab Document</DialogTitle>
            <DialogDescription>
              Upload a PDF or image and AI will extract the markers for you.
            </DialogDescription>
          </DialogHeader>

          {phase === 'pick' && (
            <Field>
              <FieldLabel>Lab file</FieldLabel>
              <div
                onDragEnter={fileActions.handleDragEnter}
                onDragLeave={fileActions.handleDragLeave}
                onDragOver={fileActions.handleDragOver}
                onDrop={fileActions.handleDrop}
                onClick={fileActions.openFileDialog}
                className={cn(
                  'flex cursor-pointer flex-col items-center justify-center gap-3 rounded-xl border-2 border-dashed py-12 transition-colors',
                  isDragging
                    ? 'border-primary bg-primary/5'
                    : 'border-border hover:border-primary/50 hover:bg-muted/40',
                )}
              >
                <Upload className="size-8 text-muted-foreground" />
                <div className="text-center">
                  <p className="text-sm font-medium">Drop a PDF or image here</p>
                  <p className="text-xs text-muted-foreground">or click to browse</p>
                </div>
                <FieldDescription>PDF, JPEG, PNG, WebP</FieldDescription>
                <input {...fileActions.getInputProps({ accept: ACCEPT })} className="sr-only" />
              </div>
              {errors.length > 0 && (
                <p className="text-sm text-destructive">{errors[0]}</p>
              )}
            </Field>
          )}

          {phase === 'extracting' && (
            <div className="flex flex-col items-center gap-4 py-10">
              <Loader2 className="size-8 animate-spin text-primary" />
              <div className="text-center">
                <p className="text-sm font-medium">Extracting lab data...</p>
                {selectedFile && (
                  <p className="mt-1 flex items-center justify-center gap-1.5 text-xs text-muted-foreground">
                    <FileText className="size-3.5" />
                    {selectedFile.name}
                  </p>
                )}
              </div>
            </div>
          )}

          {phase === 'review' && result && (
            <div className="space-y-4">
              <div className="rounded-lg border border-border bg-muted/40 px-3 py-2 text-xs text-muted-foreground">
                Extracted {result.payload.markers.length} markers &middot; confidence{' '}
                {Math.round(result.payload.confidence * 100)}% &middot; attempt
                {result.attempts > 1 ? `s ${result.attempts}` : ' 1'}
                {result.payload.confidence < 0.7 && (
                  <span className={cn('ml-1.5 font-medium', statusText.warn)}>— marked for review</span>
                )}
              </div>
              <div className="flex gap-2">
                <Button onClick={() => setConfirmOpen(true)} className="flex-1">
                  Review &amp; confirm
                </Button>
                <Button
                  variant="outline"
                  onClick={handleDirectImport}
                  disabled={importUpload.isPending}
                >
                  {importUpload.isPending ? <Loader2 className="size-4 animate-spin" /> : 'Import as-is'}
                </Button>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>

      {result && (
        <LabFormDialog
          open={confirmOpen}
          onOpenChange={(o) => {
            setConfirmOpen(o)
            if (!o) handleClose(false)
          }}
          prefill={result.payload}
          extractionMeta={{
            model: result.model,
            confidence: result.payload.confidence,
            attempts: result.attempts,
          }}
        />
      )}
    </>
  )
}
