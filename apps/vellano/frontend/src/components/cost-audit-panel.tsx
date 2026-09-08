"use client";

import {
  DataTable,
  InlineNotification,
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
} from "@carbon/react";
import { useCallback, useEffect, useState } from "react";

import {
  canViewCostAudit,
  listCostAudit,
  type UnitCostAuditEntry,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";

const AUDIT_HEADERS = [
  { key: "created_at", header: "When" },
  { key: "source", header: "Source" },
  { key: "old_cost_zar", header: "Old cost" },
  { key: "new_cost_zar", header: "New cost" },
  { key: "changed_by", header: "Changed by" },
  { key: "location_name", header: "Location" },
] as const;

type CostAuditPanelProps = {
  skuOptions: Array<{ id: string; label: string }>;
};

export function CostAuditPanel({ skuOptions }: CostAuditPanelProps) {
  const { user } = useAuth();
  const canView = canViewCostAudit(user);
  const [skuId, setSkuId] = useState("");
  const [entries, setEntries] = useState<UnitCostAuditEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadAudit = useCallback(async (selectedSkuId: string) => {
    if (!selectedSkuId) {
      setEntries([]);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const rows = await listCostAudit(selectedSkuId);
      setEntries(rows);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load cost audit");
      setEntries([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (skuOptions.length > 0 && !skuId) {
      setSkuId(skuOptions[0].id);
    }
  }, [skuOptions, skuId]);

  useEffect(() => {
    if (canView && skuId) {
      void loadAudit(skuId);
    }
  }, [canView, skuId, loadAudit]);

  if (!canView) {
    return null;
  }

  const rows = entries.map((entry) => ({
    id: entry.id,
    created_at: new Date(entry.created_at).toLocaleString("en-ZA"),
    source: entry.source,
    old_cost_zar: entry.old_cost_zar ?? "—",
    new_cost_zar: entry.new_cost_zar,
    changed_by: entry.changed_by_display_name || entry.changed_by_email,
    location_name: entry.location_name ?? "—",
  }));

  return (
    <Stack gap={4} className="vellano-cost-audit">
      <div>
        <h2 className="cds--type-productive-heading-03">Unit cost history</h2>
        <p className="cds--type-body-01">
          Audit trail for landed and corrected unit costs.
        </p>
      </div>
      {skuOptions.length === 0 ? (
        <InlineNotification
          kind="info"
          title="No SKUs"
          subtitle="Cost history appears once stock exists."
          hideCloseButton
        />
      ) : (
        <Select
          id="cost-audit-sku"
          labelText="SKU"
          value={skuId}
          onChange={(event) => setSkuId(event.target.value)}
        >
          {skuOptions.map((option) => (
            <SelectItem key={option.id} value={option.id} text={option.label} />
          ))}
        </Select>
      )}
      {error ? (
        <InlineNotification kind="error" title="Cost audit" subtitle={error} hideCloseButton />
      ) : null}
      {loading ? <p className="cds--type-body-01">Loading cost history…</p> : null}
      {!loading && skuId && entries.length === 0 ? (
        <InlineNotification
          kind="info"
          title="No audit rows"
          subtitle="Land a PO or correct a unit cost to create audit entries."
          hideCloseButton
        />
      ) : null}
      {!loading && entries.length > 0 ? (
        <DataTable rows={rows} headers={[...AUDIT_HEADERS]}>
          {({ rows: tableRows, headers, getTableProps, getHeaderProps, getRowProps }) => (
            <TableContainer title="Cost audit">
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
                  {tableRows.map((row) => (
                    <TableRow {...getRowProps({ row })} key={row.id}>
                      {row.cells.map((cell) => (
                        <TableCell key={cell.id}>{cell.value}</TableCell>
                      ))}
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          )}
        </DataTable>
      ) : null}
    </Stack>
  );
}
