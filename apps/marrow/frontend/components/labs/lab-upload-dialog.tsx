'use client'

import { useState, useRef } from 'react'
import { toast } from 'sonner'
import { Upload, Loader2, FileText } from 'lucide-react'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from '@f0rge/ui'
import { Button } from '@f0rge/ui'
import { useExtractLabUpload, useImportLabUpload } from '@/lib/api/hooks'
import { handleMutationError } from '@f0rge/ui/api'
import { LabFormDialog } from './lab-form-dialog'
import type { ExtractionResult } from '@/lib/api/types'

interface LabUploadDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
}

type Phase = 'pick' | 'extracting' | 'review' | 'done'

export function LabUploadDialog({ open, onOpenChange }: LabUploadDialogProps) {
  const [phase, setPhase] = useState<Phase>('pick')
  const [dragOver, setDragOver] = useState(false)
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [result, setResult] = useState<ExtractionResult | null>(null)
  const [confirmOpen, setConfirmOpen] = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)

  const extractUpload = useExtractLabUpload()
  const importUpload = useImportLabUpload()

  function reset() {
    setPhase('pick')
    setDragOver(false)
    setSelectedFile(null)
    setResult(null)
    setConfirmOpen(false)
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

  function handleFilePick(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (file) processFile(file)
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault()
    setDragOver(false)
    const file = e.dataTransfer.files[0]
    if (file) processFile(file)
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
            <div className="space-y-4">
              <div
                onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
                onDragLeave={() => setDragOver(false)}
                onDrop={handleDrop}
                onClick={() => fileRef.current?.click()}
                className={`flex cursor-pointer flex-col items-center justify-center gap-3 rounded-xl border-2 border-dashed py-12 transition-colors ${
                  dragOver
                    ? 'border-primary bg-primary/5'
                    : 'border-border hover:border-primary/50 hover:bg-muted/40'
                }`}
              >
                <Upload className="size-8 text-muted-foreground" />
                <div className="text-center">
                  <p className="text-sm font-medium">Drop a PDF or image here</p>
                  <p className="text-xs text-muted-foreground">or click to browse</p>
                </div>
                <p className="text-xs text-muted-foreground">PDF, JPEG, PNG, WebP</p>
                <input
                  ref={fileRef}
                  type="file"
                  accept=".pdf,image/jpeg,image/png,image/webp"
                  onChange={handleFilePick}
                  className="hidden"
                />
              </div>
            </div>
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
                  <span className="ml-1.5 font-medium text-amber-600">— marked for review</span>
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
