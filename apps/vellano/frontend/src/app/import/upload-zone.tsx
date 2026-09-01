"use client";

import { Button, FileUploaderDropContainer, FileUploaderItem, Stack, Tile } from "@carbon/react";

type UploadZoneProps = {
  title: string;
  description: string;
  file: File | null;
  disabled: boolean;
  templateLabel: string;
  onFile: (file: File | null) => void;
  onDownloadTemplate: () => void;
};

export function UploadZone({
  title,
  description,
  file,
  disabled,
  templateLabel,
  onFile,
  onDownloadTemplate,
}: UploadZoneProps) {
  return (
    <Tile>
      <Stack gap={4}>
        <div>
          <h2 className="cds--type-productive-heading-02">{title}</h2>
          <p className="cds--type-helper-text-01">{description}</p>
        </div>
        <FileUploaderDropContainer
          accept={[".csv", "text/csv"]}
          labelText="Drag and drop a CSV here or click to upload"
          multiple={false}
          disabled={disabled}
          onAddFiles={(_, { addedFiles }) => {
            const next = addedFiles[0];
            onFile(next ?? null);
          }}
        />
        {file ? (
          <FileUploaderItem
            name={file.name}
            status="complete"
            onDelete={disabled ? undefined : () => onFile(null)}
          />
        ) : null}
        <Button kind="ghost" size="sm" onClick={onDownloadTemplate}>
          {templateLabel}
        </Button>
      </Stack>
    </Tile>
  );
}
