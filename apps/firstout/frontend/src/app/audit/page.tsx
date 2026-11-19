"use client";

import {
  Button,
  InlineNotification,
  Pagination,
  Search,
  Select,
  SelectItem,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableHeader,
  TableRow,
  Tag,
} from "@carbon/react";
import { QueryClient, useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useEffect, useState } from "react";
import { PageLoading } from "@/components/page-loading";
import {
  canViewCostAudit,
  listAuditEvents,
  type AuditEvent,
  type AuditSource,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";

import { AdminPageHeader } from "@/components/administration";
import styles from "./audit.module.css";

const headers = ["When (SAST)", "Event", "Source", "Changed by"];
const timestamp = new Intl.DateTimeFormat("en-ZA", {
  dateStyle: "medium",
  timeStyle: "short",
  timeZone: "Africa/Johannesburg",
});

export default function AuditPage() {
  const { user } = useAuth();
  const [source, setSource] = useState<AuditSource | "">("");
  const [input, setInput] = useState("");
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);
  const [client] = useState(() => new QueryClient());
  const [selected, setSelected] = useState<AuditEvent | null>(null);
  const activity = useQuery(
    {
      queryKey: [
        "audit",
        user?.team.id,
        user?.id,
        canViewCostAudit(user),
        page,
        pageSize,
        source,
        query,
      ],
      queryFn: () =>
        listAuditEvents({
          limit: pageSize,
          offset: (page - 1) * pageSize,
          source: source || undefined,
          q: query,
        }),
      enabled: Boolean(user),
      retry: false,
    },
    client,
  );
  const events = activity.data?.items ?? [];

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setQuery(input.trim());
      setPage(1);
    }, 200);
    return () => window.clearTimeout(timer);
  }, [input]);

  return (
    <Stack gap={5}>
      <AdminPageHeader
        title="Audit log"
        description="Look up who changed a record or used an MCP token."
      />
      <TableContainer title="Activity register">
        <div className={styles.controls}>
          <Search
            labelText="Search activity"
            placeholder="Search by event, person or record ID"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onClear={() => setInput("")}
          />
          <Select
            id="audit-source"
            labelText="Source"
            value={source}
            onChange={(e) => {
              setSource(e.target.value as AuditSource | "");
              setPage(1);
            }}
          >
            <SelectItem value="" text="All sources" />
            <SelectItem value="mcp" text="MCP tokens" />
            <SelectItem value="books" text="Books" />
            {canViewCostAudit(user) && <SelectItem value="cost" text="Cost" />}
          </Select>
        </div>
        {activity.isError ? (
          <InlineNotification
            kind="error"
            title="Could not load activity"
            subtitle={activity.error.message}
            hideCloseButton
          >
            <Button kind="ghost" onClick={() => void activity.refetch()}>
              Try again
            </Button>
          </InlineNotification>
        ) : activity.isPending ? (
          <PageLoading
            label="Loading audit events…"
            title="Audit events"
            columns={headers}
          />
        ) : events.length ? (
          <>
            <div className={styles.overflow}>
              <Table aria-label="Audit events">
                <TableHead>
                  <TableRow>
                    {headers.map((h) => (
                      <TableHeader key={h}>{h}</TableHeader>
                    ))}
                  </TableRow>
                </TableHead>
                <TableBody>
                  {events.map((event, index) => (
                    <TableRow key={(event.href ?? "") + event.at + index}>
                      <TableCell>
                        {timestamp.format(new Date(event.at))}
                      </TableCell>
                      <TableCell>
                        <button
                          className={styles.link}
                          aria-expanded={selected === event}
                          onClick={() =>
                            setSelected(selected === event ? null : event)
                          }
                        >
                          {event.summary}
                        </button>
                      </TableCell>
                      <TableCell>
                        <Tag type={event.source === "cost" ? "purple" : "gray"}>
                          {event.source === "mcp" ? (event.origin === "firstout" ? "Firstout" : "MCP") : event.source === "cost" ? "Cost" : "Books"}
                        </Tag>
                      </TableCell>
                      <TableCell>{event.actor}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
            <Pagination
              page={page}
              pageSize={pageSize}
              pageSizes={[10, 25, 50]}
              totalItems={activity.data?.total ?? 0}
              onChange={({ page: next, pageSize: size }) => {
                setPage(size === pageSize ? next : 1);
                setPageSize(size);
              }}
            />
          </>
        ) : (
          <p className={styles.padding}>
            {query || source
              ? "No events match these filters."
              : "Activity will appear here when records change."}
          </p>
        )}
      </TableContainer>
      {selected && events.includes(selected) && (
        <section className={styles.panel}>
          <Stack gap={3}>
            <h2 className="cds--type-heading-03">{selected.summary}</h2>
            <p>
              {selected.actor} · {timestamp.format(new Date(selected.at))} SAST
            </p>
            {selected.operation_id && <p>Operation ID · {selected.operation_id}</p>}
            {selected.href && <Link className="cds--link" href={selected.href}>
              Open related record
            </Link>}
          </Stack>
        </section>
      )}
    </Stack>
  );
}
