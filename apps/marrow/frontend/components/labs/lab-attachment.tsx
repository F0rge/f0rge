'use client'

import { useState } from 'react'
import { Button, cn } from '@f0rge/ui'
import { Download, FileText } from 'lucide-react'
import type { Lab, SourceKind } from '@/lib/api/types'
import { labAttachmentSrc } from '@/lib/api/hooks/labs'

const IMAGE_EXT = /\.(png|jpe?g|webp)$/i
const PDF_EXT = /\.pdf$/i

function attachmentBasename(path: string): string {
  return path.split('/').pop() ?? path
}

function isImageAttachment(sourceKind: SourceKind, path: string): boolean {
  return sourceKind === 'image' || IMAGE_EXT.test(path)
}

function isPdfAttachment(sourceKind: SourceKind, path: string): boolean {
  return sourceKind === 'pdf' || PDF_EXT.test(path)
}

function DownloadButton({ labId, label }: { labId: number; label: string }) {
  return (
    <Button
      variant="outline"
      size="sm"
      render={<a href={labAttachmentSrc(labId, true)} />}
    >
      <Download />
      {label}
    </Button>
  )
}

function LabImageAttachment({ lab, filename }: { lab: Lab; filename: string }) {
  const [imgError, setImgError] = useState(false)
  const src = labAttachmentSrc(lab.id)

  return (
    <div className="space-y-2">
      <p className="text-xs text-muted-foreground">Source: {filename}</p>
      {!imgError ? (
        <div className="overflow-hidden rounded-lg border border-border bg-muted/30">
          <img
            src={src}
            alt={`Lab attachment: ${filename}`}
            className="max-h-64 w-full object-contain"
            onError={() => setImgError(true)}
          />
        </div>
      ) : (
        <p className="text-sm text-muted-foreground">Image could not be loaded.</p>
      )}
      <DownloadButton labId={lab.id} label="Download" />
    </div>
  )
}

function LabPdfAttachment({ lab, filename }: { lab: Lab; filename: string }) {
  const inlineSrc = labAttachmentSrc(lab.id)

  return (
    <div className="space-y-2">
      <p className="text-xs text-muted-foreground">Source: {filename}</p>
      <div className="flex flex-wrap gap-2">
        <Button
          variant="outline"
          size="sm"
          render={<a href={inlineSrc} target="_blank" rel="noopener noreferrer" />}
        >
          <FileText />
          Open PDF
        </Button>
        <DownloadButton labId={lab.id} label="Download" />
      </div>
      <div className="hidden overflow-hidden rounded-lg border border-border sm:block">
        <iframe
          src={inlineSrc}
          title={`Lab PDF: ${filename}`}
          className="h-64 w-full bg-muted/30"
        />
      </div>
    </div>
  )
}

function LabFileAttachment({ lab, filename }: { lab: Lab; filename: string }) {
  return (
    <div className="space-y-2">
      <p className="text-xs text-muted-foreground">Source attachment</p>
      <DownloadButton labId={lab.id} label={filename} />
    </div>
  )
}

interface LabAttachmentProps {
  lab: Lab
  className?: string
}

export function LabAttachment({ lab, className }: LabAttachmentProps) {
  if (!lab.attachment_path) return null

  const filename = attachmentBasename(lab.attachment_path)
  const { source_kind, attachment_path } = lab

  return (
    <div className={cn('min-w-0', className)}>
      {isImageAttachment(source_kind, attachment_path) ? (
        <LabImageAttachment lab={lab} filename={filename} />
      ) : isPdfAttachment(source_kind, attachment_path) ? (
        <LabPdfAttachment lab={lab} filename={filename} />
      ) : (
        <LabFileAttachment lab={lab} filename={filename} />
      )}
    </div>
  )
}
