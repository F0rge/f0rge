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
import { useCallback, useEffect, useState } from "react";

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
  const [events, setEvents] = useState<BooksEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const rows = await listBooksEvents(documentType, documentId);
      setEvents(rows);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load history.");
      setEvents([]);
    } finally {
      setLoading(false);
    }
  }, [documentType, documentId]);

  useEffect(() => {
    void load();
  }, [load]);

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
