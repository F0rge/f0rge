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
  downloadSkuCriticalityCsv,
  formatZarAmount,
  type SkuCriticalityReport,
} from "@/lib/api";
import { abcTagType, buildCriticalitySummary, formatSharePct } from "@/lib/criticality";

const SKU_HEADERS = [
  { key: "our_ref", header: "Our ref" },
  { key: "name", header: "Name" },
  { key: "category", header: "Category" },
  { key: "qty", header: "Qty" },
  { key: "value_zar", header: "Value" },
  { key: "share_pct", header: "Share %" },
  { key: "cumulative_pct", header: "Cumulative %" },
  { key: "abc_class", header: "ABC" },
  { key: "band_50", header: "50% band" },
] as const;

const CATEGORY_HEADERS = [
  { key: "category", header: "Category" },
  { key: "qty", header: "Qty" },
  { key: "value_zar", header: "Value" },
  { key: "share_pct", header: "Share %" },
  { key: "cumulative_pct", header: "Cumulative %" },
  { key: "abc_class", header: "ABC" },
] as const;

type CriticalityReportProps = {
  report: SkuCriticalityReport;
  fromDate: string;
  toDate: string;
  error: string | null;
  onCsvError: (message: string) => void;
};

function AbcTag({ abcClass }: { abcClass: "A" | "B" | "C" }) {
  return (
    <Tag type={abcTagType(abcClass)} size="sm">
      {abcClass}
    </Tag>
  );
}

function Band50Marker({ hits }: { hits: boolean }) {
  if (!hits) {
    return "—";
  }
  return (
    <Tag type="purple" size="sm">
      50%
    </Tag>
  );
}

export function CriticalityReport({
  report,
  fromDate,
  toDate,
  error,
  onCsvError,
}: CriticalityReportProps) {
  async function handleCsv() {
    try {
      await downloadSkuCriticalityCsv(fromDate, toDate);
    } catch (err) {
      onCsvError(err instanceof Error ? err.message : "Failed to download CSV.");
    }
  }

  const skuRows = report.lines.map((line) => ({
    id: line.sku_id,
    our_ref: line.our_ref,
    name: line.name,
    category: line.category ?? "—",
    qty: String(line.qty),
    value_zar: formatZarAmount(line.value_zar),
    share_pct: formatSharePct(line.share_pct),
    cumulative_pct: formatSharePct(line.cumulative_pct),
    abc_class: line.abc_class,
    band_50: line.hits_50pct_band ? "yes" : "",
  }));

  const categoryRows = report.categories.map((line) => ({
    id: line.category,
    category: line.category,
    qty: String(line.qty),
    value_zar: formatZarAmount(line.value_zar),
    share_pct: formatSharePct(line.share_pct),
    cumulative_pct: formatSharePct(line.cumulative_pct),
    abc_class: line.abc_class,
  }));

  const skuById = new Map(report.lines.map((line) => [line.sku_id, line]));
  const categoryByName = new Map(report.categories.map((line) => [line.category, line]));

  return (
    <Stack gap={6}>
      <Stack gap={4} orientation="horizontal">
        <p className="cds--type-body-01">
          {report.from_date} to {report.to_date} — {buildCriticalitySummary(report)}
        </p>
        <Button kind="tertiary" onClick={() => void handleCsv()}>
          Download CSV
        </Button>
      </Stack>
      {error ? (
        <InlineNotification
          kind="error"
          title="Criticality"
          subtitle={error}
          hideCloseButton
          lowContrast
        />
      ) : null}
      {report.lines.length === 0 ? (
        error ? null : (
          <InlineNotification
            kind="info"
            title="No SKU sales"
            subtitle="No invoice lines with SKUs in this date range."
            hideCloseButton
            lowContrast
          />
        )
      ) : (
        <DataTable rows={skuRows} headers={[...SKU_HEADERS]}>
          {({ rows, headers, getTableProps, getHeaderProps, getRowProps }) => (
            <TableContainer title="SKU criticality">
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
                            {cell.info.header === "abc_class" && source ? (
                              <AbcTag abcClass={source.abc_class} />
                            ) : cell.info.header === "band_50" && source ? (
                              <Band50Marker hits={source.hits_50pct_band} />
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
      {report.categories.length > 0 ? (
        <Stack gap={4}>
          <p className="cds--type-productive-heading-02">By category</p>
          <DataTable rows={categoryRows} headers={[...CATEGORY_HEADERS]}>
            {({ rows, headers, getTableProps, getHeaderProps, getRowProps }) => (
              <TableContainer title="Category criticality">
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
                      const source = categoryByName.get(row.id);
                      return (
                        <TableRow {...getRowProps({ row })} key={row.id}>
                          {row.cells.map((cell) => (
                            <TableCell key={cell.id}>
                              {cell.info.header === "abc_class" && source ? (
                                <AbcTag abcClass={source.abc_class} />
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
        </Stack>
      ) : null}
    </Stack>
  );
}
