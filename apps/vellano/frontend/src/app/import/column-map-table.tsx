"use client";

import {
  Select,
  SelectItem,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableHeader,
  TableRow,
} from "@carbon/react";

import type { MapField } from "./import-maps";

type ColumnMapTableProps = {
  idPrefix: string;
  title: string;
  description: string;
  headers: string[];
  sampleRow: Record<string, string> | null;
  headerToField: Record<string, string>;
  fields: readonly MapField[];
  disabled: boolean;
  onChange: (header: string, field: string) => void;
};

export function ColumnMapTable({
  idPrefix,
  title,
  description,
  headers,
  sampleRow,
  headerToField,
  fields,
  disabled,
  onChange,
}: ColumnMapTableProps) {
  const mapped = new Set(Object.values(headerToField).filter(Boolean));
  const missingRequired = fields.filter((field) => field.required && !mapped.has(field.key));

  return (
    <TableContainer title={title} description={description}>
      {missingRequired.length > 0 ? (
        <p className="cds--type-helper-text-01">
          Required: {missingRequired.map((field) => field.label).join(", ")}
        </p>
      ) : null}
      <Table>
        <TableHead>
          <TableRow>
            <TableHeader>CSV header</TableHeader>
            <TableHeader>Map to field</TableHeader>
            <TableHeader>Sample</TableHeader>
          </TableRow>
        </TableHead>
        <TableBody>
          {headers.map((header, index) => (
            <TableRow key={header}>
              <TableCell>{header}</TableCell>
              <TableCell>
                <Select
                  id={`map-${idPrefix}-${index}`}
                  labelText="Map to field"
                  hideLabel
                  size="sm"
                  disabled={disabled}
                  value={headerToField[header] ?? ""}
                  onChange={(event) => onChange(header, event.target.value)}
                >
                  <SelectItem value="" text="Ignore" />
                  {fields.map((field) => (
                    <SelectItem
                      key={field.key}
                      value={field.key}
                      text={field.required ? `${field.label} (required)` : field.label}
                    />
                  ))}
                </Select>
              </TableCell>
              <TableCell>{sampleRow?.[header] ?? "—"}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </TableContainer>
  );
}
