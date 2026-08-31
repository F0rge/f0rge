'use client'

import { useState } from 'react'
import { Button, cn } from '@f0rge/ui'
import { Download, FileText } from 'lucide-react'
import type { Lab, SourceKind } from '@/lib/api/types'
import { labAttachmentSrc } from '@/lib/api/hooks/labs'
import { humanSourceFilename } from './lab-attachment-label'

const IMAGE_EXT = /\.(png|jpe?g|webp)$/i
const PDF_EXT = /\.pdf$/i
const TOUCH_BTN = 'h-11 min-h-11 min-w-0'

function isImageAttachment(sourceKind: SourceKind, path: string): boolean {
  return sourceKind === 'image' || IMAGE_EXT.test(path)
}

function isPdfAttachment(sourceKind: SourceKind, path: string): boolean {
  return sourceKind === 'pdf' || PDF_EXT.test(path)
}

function DownloadButton({ labId, className }: { labId: number; className?: string }) {
  return (
    <Button
      variant="outline"
      nativeButton={false}
      className={cn(TOUCH_BTN, className)}
      render={<a href={labAttachmentSrc(labId, true)} />}
    >
      <Download />
      Download
    </Button>
  )
}

function SourceFilename({ filename }: { filename: string | null }) {
  if (!filename) return null
  return (
    <p className="min-w-0 truncate text-xs text-muted-foreground" title={filename}>
      {filename}
    </p>
  )
}

function LabImageAttachment({ lab }: { lab: Lab }) {
  const [imgError, setImgError] = useState(false)
  const src = labAttachmentSrc(lab.id)

  return (
    <div className="min-w-0 space-y-2">
      <SourceFilename filename={humanSourceFilename(lab.source_path)} />
      {!imgError ? (
        <a
          href={src}
          target="_blank"
          rel="noopener noreferrer"
          className="-mx-4 block min-w-0 overflow-hidden bg-muted/30 lg:mx-0 lg:rounded-lg lg:border lg:border-border"
          aria-label="View original image"
        >
          <img
            src={src}
            alt="Lab scan"
            className="max-h-[min(70dvh,36rem)] w-full cursor-zoom-in object-contain"
            onError={() => setImgError(true)}
          />
        </a>
      ) : (
        <p className="text-sm text-muted-foreground">Image could not be loaded.</p>
      )}
      <DownloadButton labId={lab.id} className="w-full sm:w-auto" />
    </div>
  )
}

function LabPdfAttachment({ lab, preview }: { lab: Lab; preview: boolean }) {
  const inlineSrc = labAttachmentSrc(lab.id)

  return (
    <div className="min-w-0 space-y-2">
      <SourceFilename filename={humanSourceFilename(lab.source_path)} />
      <div className="flex min-w-0 flex-col gap-2 sm:flex-row sm:flex-wrap">
        <Button
          nativeButton={false}
          className={cn(TOUCH_BTN, 'w-full sm:w-auto')}
          render={<a href={inlineSrc} target="_blank" rel="noopener noreferrer" />}
        >
          <FileText />
          Open PDF
        </Button>
        <DownloadButton labId={lab.id} className="w-full sm:w-auto" />
      </div>
      {preview ? (
        <div className="min-w-0 overflow-hidden rounded-lg border border-border">
          <iframe
            src={inlineSrc}
            title="Lab PDF preview"
            className="h-64 w-full bg-muted/30"
          />
        </div>
      ) : null}
    </div>
  )
}

function LabFileAttachment({ lab }: { lab: Lab }) {
  return (
    <div className="min-w-0">
      <DownloadButton labId={lab.id} className="w-full sm:w-auto" />
    </div>
  )
}

interface LabAttachmentProps {
  lab: Lab
  className?: string
  /** Desktop inline panel only — skip iframe PDF on the mobile sheet. */
  pdfPreview?: boolean
}

export function LabAttachment({ lab, className, pdfPreview = false }: LabAttachmentProps) {
  if (!lab.attachment_path) return null

  const { source_kind, attachment_path } = lab

  return (
    <div className={cn('min-w-0', className)}>
      {isImageAttachment(source_kind, attachment_path) ? (
        <LabImageAttachment lab={lab} />
      ) : isPdfAttachment(source_kind, attachment_path) ? (
        <LabPdfAttachment lab={lab} preview={pdfPreview} />
      ) : (
        <LabFileAttachment lab={lab} />
      )}
    </div>
  )
}
