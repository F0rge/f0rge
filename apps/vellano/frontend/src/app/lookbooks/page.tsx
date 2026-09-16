"use client";

import {
  Button,
  DataTable,
  InlineNotification,
  Modal,
  Pagination,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableHeader,
  TableRow,
  Tabs,
  Tab,
  TabList,
  TabPanels,
  TabPanel,
} from "@carbon/react";
import { useCallback, useEffect, useMemo, useState, Suspense } from "react";

import {
  ApiError,
  canMutateQuotes,
  formatZarAmount,
  getLookbook,
  listLookbooks,
  lookbookPublicUrl,
  revokeLookbook,
  type Lookbook,
  type LookbookListItem,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";

const TABLE_HEADERS = [
  { key: "name", header: "Name" },
  { key: "customer_name", header: "Customer" },
  { key: "sku_count", header: "SKUs" },
  { key: "expires_at", header: "Expires" },
  { key: "status", header: "Status" },
  { key: "actions", header: "Action" },
] as const;

type LookbookRow = {
  id: string;
  name: string;
  customer_name: string;
  sku_count: string;
  expires_at: string;
  status: string;
  actions: string;
};

function statusLabel(row: LookbookListItem): string {
  if (row.revoked_at) {
    return "Revoked";
  }
  if (new Date(row.expires_at).getTime() <= Date.now()) {
    return "Expired";
  }
  return "Live";
}

function LookbooksPageInner() {
  const { user } = useAuth();
  const canMutate = canMutateQuotes(user);
  const [rows, setRows] = useState<LookbookListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [copied, setCopied] = useState<string | null>(null);
  const [detail, setDetail] = useState<Lookbook | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const pageData = await listLookbooks({ limit: pageSize, offset: (page - 1) * pageSize });
      setRows(pageData.items);
      setTotal(pageData.total);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load lookbooks");
    } finally {
      setLoading(false);
    }
  }, [page, pageSize]);

  useEffect(() => {
    if (user) {
      void load();
    }
  }, [user, load]);

  const tableRows: LookbookRow[] = useMemo(
    () =>
      rows.map((row) => ({
        id: row.id,
        name: row.name,
        customer_name: row.customer_name ?? "Walk-in",
        sku_count: String(row.sku_count),
        expires_at: new Date(row.expires_at).toLocaleDateString("en-ZA"),
        status: statusLabel(row),
        actions: row.id,
      })),
    [rows],
  );

  async function onCopy(row: LookbookListItem) {
    const url = lookbookPublicUrl(row.token);
    try {
      await navigator.clipboard.writeText(url);
      setCopied(url);
    } catch {
      setCopied(url);
    }
  }

  async function onRevoke(id: string) {
    setError(null);
    try {
      await revokeLookbook(id);
      await load();
      if (detail?.id === id) {
        setDetail(await getLookbook(id));
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not revoke lookbook");
    }
  }

  async function onOpen(id: string) {
    setError(null);
    try {
      setDetail(await getLookbook(id));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not open lookbook");
    }
  }

  return (
    <Stack gap={6}>
      <div className="vellano-page-header">
        <div>
          <h1 className="cds--type-productive-heading-04">Lookbooks</h1>
          <p className="cds--type-body-01">Shared catalogue links for walk-ins and CRM customers.</p>
        </div>
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
      {copied ? (
        <InlineNotification
          kind="success"
          title="Link copied"
          subtitle={copied}
          onCloseButtonClick={() => setCopied(null)}
          lowContrast
        />
      ) : null}
      {loading ? <p className="cds--type-body-01">Loading lookbooks…</p> : null}
      <DataTable rows={tableRows} headers={[...TABLE_HEADERS]}>
        {({ rows: tableBody, headers, getHeaderProps, getRowProps, getTableProps }) => (
          <TableContainer>
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
                {tableBody.map((row) => {
                  const source = rows.find((item) => item.id === row.id);
                  return (
                    <TableRow
                      {...getRowProps({ row })}
                      key={row.id}
                      onClick={() => void onOpen(row.id)}
                    >
                      {row.cells.map((cell) => {
                        if (cell.info.header === "actions" && source) {
                          return (
                            <TableCell key={cell.id} onClick={(event) => event.stopPropagation()}>
                              <Stack gap={2} orientation="horizontal">
                                <Button kind="ghost" size="sm" onClick={() => void onCopy(source)}>
                                  Copy link
                                </Button>
                                {canMutate && !source.revoked_at ? (
                                  <Button
                                    kind="danger--ghost"
                                    size="sm"
                                    onClick={() => void onRevoke(source.id)}
                                  >
                                    Revoke
                                  </Button>
                                ) : null}
                              </Stack>
                            </TableCell>
                          );
                        }
                        return <TableCell key={cell.id}>{cell.value}</TableCell>;
                      })}
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
      <Modal
        open={Boolean(detail)}
        modalHeading={detail?.name ?? "Lookbook"}
        passiveModal
        onRequestClose={() => setDetail(null)}
      >
        {detail ? (
          <Tabs>
            <TabList aria-label="Lookbook detail">
              <Tab>Items</Tab>
              <Tab>Activity</Tab>
            </TabList>
            <TabPanels>
              <TabPanel>
                <p className="cds--type-body-01">
                  {detail.customer_name ?? "Walk-in"} · {detail.sku_count} SKUs · {statusLabel(detail)}
                </p>
                <ul className="cds--type-body-01">
                  {detail.items.map((item) => (
                    <li key={item.id}>
                      {item.our_ref} — {item.name}
                      {item.unit_inc_vat ? ` · ${formatZarAmount(item.unit_inc_vat)}` : ""}
                    </li>
                  ))}
                </ul>
              </TabPanel>
              <TabPanel>
                <p className="cds--type-body-01">Activity lands in a later slice. Opens, dwell, and hearts will show here.</p>
              </TabPanel>
            </TabPanels>
          </Tabs>
        ) : null}
      </Modal>
    </Stack>
  );
}

export default function LookbooksPage() {
  return (
    <Suspense fallback={<p className="cds--type-body-01">Loading lookbooks…</p>}>
      <LookbooksPageInner />
    </Suspense>
  );
}
