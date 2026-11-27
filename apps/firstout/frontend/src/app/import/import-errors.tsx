"use client";

import {
  Link,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableHeader,
  TableRow,
} from "@carbon/react";

import type { CatalogueImportError } from "@/lib/api";

type ImportErrorsProps = {
  errors: CatalogueImportError[];
};

export function ImportErrors({ errors }: ImportErrorsProps) {
  return (
    <TableContainer
      title={`Validation errors (${errors.length})`}
      description="Fix these rows in the CSV and re-preview."
    >
      <Table>
        <TableHead>
          <TableRow>
            <TableHeader>File</TableHeader>
            <TableHeader>Row</TableHeader>
            <TableHeader>Message</TableHeader>
          </TableRow>
        </TableHead>
        <TableBody>
          {errors.map((entry, index) => (
            <TableRow key={`${entry.file}-${entry.row}-${index}`}>
              <TableCell>{entry.file === "inventory" ? "Inventory" : "Stock on Hand"}</TableCell>
              <TableCell>{entry.row}</TableCell>
              <TableCell>
                {entry.message}
                {/* "Unknown category 'X'. Add it in Settings first." and the sub-category twin. */}
                {/add it in settings first/i.test(entry.message) && (
                  <>
                    {" "}
                    <Link href="/settings/categories" inline>Open Settings → Categories</Link>
                  </>
                )}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </TableContainer>
  );
}
