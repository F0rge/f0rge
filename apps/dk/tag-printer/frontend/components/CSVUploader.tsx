'use client';

import { ChangeEvent, DragEvent, useRef, useState } from 'react';
import { FileText, Loader2, Upload } from 'lucide-react';
import { toast } from 'sonner';
import { cn } from '@/lib/utils';

interface CSVUploaderProps {
  onFileUpload: (file: File) => void;
  isLoading?: boolean;
}

export default function CSVUploader({ onFileUpload, isLoading }: CSVUploaderProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [fileName, setFileName] = useState<string | null>(null);

  const acceptFile = (file: File | undefined) => {
    if (file && file.name.toLowerCase().endsWith('.csv')) {
      setFileName(file.name);
      onFileUpload(file);
    } else {
      toast.error('Please upload a valid CSV file');
    }
  };

  const handleFileChange = (e: ChangeEvent<HTMLInputElement>) => {
    acceptFile(e.target.files?.[0]);
  };

  const handleDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(false);
    if (isLoading) return;
    acceptFile(e.dataTransfer.files?.[0]);
  };

  const openPicker = () => {
    if (!isLoading) inputRef.current?.click();
  };

  return (
    <div
      data-tour="upload"
      role="button"
      tabIndex={0}
      onClick={openPicker}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          openPicker();
        }
      }}
      onDragOver={(e) => {
        e.preventDefault();
        if (!isLoading) setIsDragging(true);
      }}
      onDragLeave={() => setIsDragging(false)}
      onDrop={handleDrop}
      className={cn(
        'flex cursor-pointer flex-col items-center rounded-xl border-2 border-dashed border-border bg-card p-8 text-center transition-colors',
        isDragging && 'border-ring bg-accent/50',
        isLoading && 'pointer-events-none opacity-60'
      )}
    >
      <input
        ref={inputRef}
        type="file"
        accept=".csv"
        onChange={handleFileChange}
        disabled={isLoading}
        className="hidden"
      />

      {isLoading ? (
        <>
          <Loader2 className="mb-3 h-8 w-8 animate-spin text-muted-foreground" />
          <p className="text-sm text-muted-foreground">Uploading…</p>
        </>
      ) : fileName ? (
        <>
          <FileText className="mb-3 h-8 w-8 text-muted-foreground" />
          <p className="text-sm font-medium">{fileName}</p>
          <p className="mt-1 text-xs text-muted-foreground">Click or drop to replace</p>
        </>
      ) : (
        <>
          <Upload className="mb-3 h-8 w-8 text-muted-foreground" />
          <p className="text-sm font-medium">Drag &amp; drop your CSV here, or click to browse</p>
          <p className="mt-1 text-xs text-muted-foreground">DEAR Inventory CSV export</p>
        </>
      )}
    </div>
  );
}
