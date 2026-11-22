"use client";

import {
  InlineNotification,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableHeader,
  TableRow,
} from "@carbon/react";
import { useQuery } from "@tanstack/react-query";

import {
  listBooksEvents,
  type BooksDocumentType,
  type BooksEvent,
} from "@/lib/api";

type BooksHistoryProps = {
  documentType: BooksDocumentType;
  documentId: string;
};

function formatWhen(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) {
    return iso;
  }
  return date.toLocaleString("en-ZA");
}

export function BooksHistory({ documentType, documentId }: BooksHistoryProps) {
  const history = useQuery({
    queryKey: ["books-events", { documentType, documentId }],
    queryFn: () => listBooksEvents(documentType, documentId),
  });
  const events: BooksEvent[] = (history.isError ? undefined : history.data) ?? [];
  const loading = history.isPending || history.isFetching;
  const error = history.error ? history.error.message || "Failed to load history." : null;

  return (
    <TableContainer title="History">
      {error ? (
        <InlineNotification
          kind="error"
          title="History"
          subtitle={error}
          hideCloseButton
          lowContrast
        />
      ) : null}
      {loading ? (
        <p className="cds--type-body-01">Loading history…</p>
      ) : events.length === 0 ? (
        <p className="cds--type-body-01">No history yet.</p>
      ) : (
        <Table>
          <TableHead>
            <TableRow>
              <TableHeader>When</TableHeader>
              <TableHeader>Action</TableHeader>
              <TableHeader>Actor</TableHeader>
              <TableHeader>Note</TableHeader>
            </TableRow>
          </TableHead>
          <TableBody>
            {events.map((event) => (
              <TableRow key={event.id}>
                <TableCell>{formatWhen(event.created_at)}</TableCell>
                <TableCell>{event.action}</TableCell>
                <TableCell>{event.actor_email ?? "—"}</TableCell>
                <TableCell>{event.note ?? "—"}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </TableContainer>
  );
}
