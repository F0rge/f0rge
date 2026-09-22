// Superdesign skipped — implemented Carbon DataTable from /invoices pagination pattern (CLI available).
"use client";

import {
  DataTable,
  InlineNotification,
  Pagination,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableHeader,
  TableRow,
} from "@carbon/react";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";

import { listAuditEvents, type AuditEvent, type AuditSource } from "@/lib/api";
import { useAuth } from "@/lib/auth";

const TABLE_HEADERS = [
  { key: "at", header: "When" },
  { key: "source", header: "Source" },
  { key: "actor", header: "Actor" },
  { key: "summary", header: "Summary" },
] as const;

type AuditRow = {
  id: string;
  at: string;
  source: string;
  actor: string;
  summary: string;
  href: string;
};

function formatAuditAt(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString("en-GB", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function sourceLabel(source: AuditSource): string {
  if (source === "nia") {
    return "Nia";
  }
  if (source === "cost") {
    return "Cost";
  }
  return "Books";
}

export default function AuditPage() {
  const router = useRouter();
  const { user } = useAuth();
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadEvents = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await listAuditEvents({
        limit: pageSize,
        offset: (page - 1) * pageSize,
      });
      setEvents(response.items);
      setTotal(response.total);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load audit events.");
      setEvents([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }, [page, pageSize]);

  useEffect(() => {
    if (user) {
      void loadEvents();
    }
  }, [user, loadEvents]);

  const hrefById = useMemo(
    () =>
      Object.fromEntries(
        events.map((event, index) => [`${event.at}-${index}`, event.href] as const),
      ),
    [events],
  );

  const rows: AuditRow[] = useMemo(
    () =>
      events.map((event, index) => ({
        id: `${event.at}-${index}`,
        at: formatAuditAt(event.at),
        source: sourceLabel(event.source),
        actor: event.actor,
        summary: event.summary,
        href: event.href,
      })),
    [events],
  );

  return (
    <Stack gap={6}>
      <div>
        <h1 className="cds--type-productive-heading-04">Audit</h1>
        <p className="cds--type-body-01">
          Unified activity across books, Nia, and cost audit. Select a row to open the related
          document.
        </p>
      </div>

      {error ? (
        <InlineNotification
          kind="error"
          title="Error"
          subtitle={error}
          onCloseButtonClick={() => setError(null)}
          lowContrast
        />
      ) : null}

      {loading ? (
        <p className="cds--type-body-01">Loading audit events…</p>
      ) : total === 0 && !error ? (
        <InlineNotification
          kind="info"
          title="No events"
          subtitle="Audit events will appear here as books, Nia, and cost activity occurs."
          hideCloseButton
          lowContrast
        />
      ) : (
        <>
          <DataTable rows={rows} headers={[...TABLE_HEADERS]}>
            {({ rows: tableRows, headers, getTableProps, getHeaderProps, getRowProps }) => (
              <TableContainer title="Audit events">
                <Table {...getTableProps()}>
                  <TableHead>
                    <TableRow>
                      {headers.map((header) => (
                        <TableHeader {...getHeaderProps({ header })} key={header.key}>
                          {header.header}
                        </TableHeader>
                      ))}
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {tableRows.map((row) => {
                      const href = hrefById[row.id];
                      return (
                        <TableRow
                          {...getRowProps({ row })}
                          key={row.id}
                          style={{ cursor: href ? "pointer" : undefined }}
                          onClick={() => {
                            if (href) {
                              router.push(href);
                            }
                          }}
                        >
                          {row.cells.map((cell) => (
                            <TableCell key={cell.id}>{cell.value}</TableCell>
                          ))}
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              </TableContainer>
            )}
          </DataTable>
          <Pagination
            page={page}
            pageSize={pageSize}
            pageSizes={[10, 25, 50]}
            totalItems={total}
            onChange={({ page: nextPage, pageSize: nextSize }) => {
              setPage(nextPage);
              setPageSize(nextSize);
            }}
          />
        </>
      )}
    </Stack>
  );
}
