"use client";

import {
  Button,
  DataTable,
  InlineNotification,
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

import {
  downloadSkuLeadTimesCsv,
  downloadSupplierLeadTimesCsv,
  type SkuLeadTimeRow,
  type SupplierLeadTimeRow,
} from "@/lib/api";
import { formatLeadDays, isWeakLeadTimeSample } from "@/lib/lead-times";

const SUPPLIER_HEADERS = [
  { key: "supplier_name", header: "Supplier" },
  { key: "n", header: "n" },
  { key: "median_days", header: "Median PO→receive" },
  { key: "median_last_3_days", header: "Last 3" },
  { key: "median_water_days", header: "Water median" },
  { key: "p90_days", header: "P90" },
] as const;

const SKU_HEADERS = [
  { key: "our_ref", header: "Our ref" },
  { key: "name", header: "Name" },
  { key: "n", header: "n" },
  { key: "manual_lead_time_days", header: "Manual lead time" },
  { key: "median_days", header: "Observed median" },
  { key: "median_last_3_days", header: "Last 3" },
  { key: "median_water_days", header: "Water median" },
  { key: "p90_days", header: "P90" },
] as const;

type LeadTimesReportProps = {
  suppliers: SupplierLeadTimeRow[];
  skus: SkuLeadTimeRow[];
  error: string | null;
  onCsvError: (message: string) => void;
};

function Last3Cell({ days, n }: { days: number; n: number }) {
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: "0.5rem" }}>
      {formatLeadDays(days)}
      {isWeakLeadTimeSample(n) ? (
        <Tag type="magenta" size="sm">
          Weak
        </Tag>
      ) : null}
    </span>
  );
}

export function LeadTimesReport({ suppliers, skus, error, onCsvError }: LeadTimesReportProps) {
  async function handleCsv(download: () => Promise<void>) {
    try {
      await download();
    } catch (err) {
      onCsvError(err instanceof Error ? err.message : "Failed to download CSV.");
    }
  }

  const supplierRows = suppliers.map((row) => ({
    id: row.supplier_id,
    supplier_name: row.supplier_name,
    n: String(row.n),
    median_days: formatLeadDays(row.median_days),
    median_last_3_days: row.supplier_id,
    median_water_days: formatLeadDays(row.median_water_days),
    p90_days: formatLeadDays(row.p90_days),
  }));

  const skuRows = skus.map((row) => ({
    id: row.sku_id,
    our_ref: row.our_ref,
    name: row.name,
    n: String(row.n),
    manual_lead_time_days: formatLeadDays(row.manual_lead_time_days),
    median_days: formatLeadDays(row.median_days),
    median_last_3_days: row.sku_id,
    median_water_days: formatLeadDays(row.median_water_days),
    p90_days: formatLeadDays(row.p90_days),
  }));

  const supplierById = new Map(suppliers.map((row) => [row.supplier_id, row]));
  const skuById = new Map(skus.map((row) => [row.sku_id, row]));

  return (
    <Stack gap={6}>
      <p className="cds--type-body-01">
        Lifetime completed purchase orders. Last-3 is marked Weak when n &lt; 3.
      </p>
      {error ? (
        <InlineNotification
          kind="error"
          title="Lead times"
          subtitle={error}
          hideCloseButton
          lowContrast
        />
      ) : null}
      <Stack gap={4}>
        <Stack gap={4} orientation="horizontal">
          <p className="cds--type-productive-heading-02">Suppliers</p>
          <Button
            kind="tertiary"
            onClick={() => void handleCsv(downloadSupplierLeadTimesCsv)}
          >
            Download CSV
          </Button>
        </Stack>
        {suppliers.length === 0 ? (
          error ? null : (
            <InlineNotification
              kind="info"
              title="No supplier lead times"
              subtitle="No completed purchase orders yet."
              hideCloseButton
              lowContrast
            />
          )
        ) : (
          <DataTable rows={supplierRows} headers={[...SUPPLIER_HEADERS]}>
            {({ rows, headers, getTableProps, getHeaderProps, getRowProps }) => (
              <TableContainer title="Supplier lead times">
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
                    {rows.map((row) => {
                      const source = supplierById.get(row.id);
                      return (
                        <TableRow {...getRowProps({ row })} key={row.id}>
                          {row.cells.map((cell) => (
                            <TableCell key={cell.id}>
                              {cell.info.header === "median_last_3_days" && source ? (
                                <Last3Cell days={source.median_last_3_days} n={source.n} />
                              ) : (
                                cell.value
                              )}
                            </TableCell>
                          ))}
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              </TableContainer>
            )}
          </DataTable>
        )}
      </Stack>
      <Stack gap={4}>
        <Stack gap={4} orientation="horizontal">
          <p className="cds--type-productive-heading-02">SKUs</p>
          <Button kind="tertiary" onClick={() => void handleCsv(downloadSkuLeadTimesCsv)}>
            Download CSV
          </Button>
        </Stack>
        {skus.length === 0 ? (
          error ? null : (
            <InlineNotification
              kind="info"
              title="No SKU lead times"
              subtitle="No completed purchase orders yet."
              hideCloseButton
              lowContrast
            />
          )
        ) : (
          <DataTable rows={skuRows} headers={[...SKU_HEADERS]}>
            {({ rows, headers, getTableProps, getHeaderProps, getRowProps }) => (
              <TableContainer title="SKU lead times">
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
                    {rows.map((row) => {
                      const source = skuById.get(row.id);
                      return (
                        <TableRow {...getRowProps({ row })} key={row.id}>
                          {row.cells.map((cell) => (
                            <TableCell key={cell.id}>
                              {cell.info.header === "median_last_3_days" && source ? (
                                <Last3Cell days={source.median_last_3_days} n={source.n} />
                              ) : (
                                cell.value
                              )}
                            </TableCell>
                          ))}
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              </TableContainer>
            )}
          </DataTable>
        )}
      </Stack>
    </Stack>
  );
}
