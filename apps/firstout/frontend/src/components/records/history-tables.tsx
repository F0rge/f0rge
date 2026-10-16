"use client";

import { Tag } from "@carbon/react";
import Link from "next/link";
import { useCallback } from "react";

import {
  formatZarAmount,
  listPurchaseHistory,
  listSalesHistory,
  listSupplierPrices,
  type ListParams,
  type PurchaseHistoryRow,
  type SalesHistoryRow,
  type SupplierPriceRow,
} from "@/lib/api";

import { RecordsTable, type RecordsColumn } from "./records-table";

function money(currency: string, value: string | null): string {
  return value === null ? "—" : `${currency} ${value}`;
}

const SALES_COLUMNS: RecordsColumn<SalesHistoryRow>[] = [
  { key: "issue_date", header: "Date", render: (row) => row.issue_date },
  {
    key: "document_number",
    header: "Document",
    render: (row) => (
      <>
        {row.document_number}{" "}
        {row.kind === "credit_note" ? (
          <Tag size="sm" type="purple">
            Credit
          </Tag>
        ) : null}
      </>
    ),
  },
  {
    key: "customer_name",
    header: "Customer",
    render: (row) =>
      row.customer_id ? (
        <Link href={`/customers/${row.customer_id}`}>{row.customer_name ?? "—"}</Link>
      ) : (
        "—"
      ),
  },
  { key: "our_ref", header: "SKU", render: (row) => row.our_ref ?? "—" },
  { key: "description", header: "Product", render: (row) => row.description },
  { key: "qty", header: "Qty", render: (row) => Number(row.qty).toString() },
  { key: "ex_vat", header: "Ex VAT", render: (row) => formatZarAmount(row.ex_vat) },
  { key: "inc_vat", header: "Inc VAT", render: (row) => formatZarAmount(row.inc_vat) },
];

const PURCHASE_COLUMNS: RecordsColumn<PurchaseHistoryRow>[] = [
  { key: "issue_date", header: "Date", render: (row) => row.issue_date },
  { key: "bill_number", header: "Bill", render: (row) => row.bill_number },
  {
    key: "supplier_name",
    header: "Supplier",
    render: (row) => <Link href={`/suppliers/${row.supplier_id}`}>{row.supplier_name}</Link>,
  },
  { key: "description", header: "Product", render: (row) => row.description },
  { key: "qty", header: "Qty", render: (row) => row.qty },
  { key: "unit_amount", header: "Unit", render: (row) => money(row.currency, row.unit_amount) },
  {
    key: "amount_foreign",
    header: "Line total",
    render: (row) => money(row.currency, row.amount_foreign),
  },
  {
    key: "bill_amount_zar",
    header: "Bill in ZAR",
    render: (row) =>
      row.fx_rate_known ? (
        formatZarAmount(row.bill_amount_zar)
      ) : (
        <Tag size="sm" type="warm-gray">
          No ZAR rate
        </Tag>
      ),
  },
];

const PRICE_COLUMNS: RecordsColumn<SupplierPriceRow>[] = [
  {
    key: "supplier_name",
    header: "Supplier",
    render: (row) => <Link href={`/suppliers/${row.supplier_id}`}>{row.supplier_name}</Link>,
  },
  {
    key: "our_ref",
    header: "SKU",
    render: (row) => <Link href={`/catalogue/${row.sku_id}`}>{row.our_ref}</Link>,
  },
  { key: "sku_name", header: "Product", render: (row) => row.sku_name },
  { key: "supplier_sku", header: "Supplier SKU", render: (row) => row.supplier_sku ?? "—" },
  { key: "latest_price", header: "Latest", render: (row) => money(row.currency, row.latest_price) },
  { key: "fixed_price", header: "Fixed", render: (row) => money(row.currency, row.fixed_price) },
];

export function SalesHistoryTable({ customerId }: { customerId?: string }) {
  const load = useCallback(
    (params: ListParams) => listSalesHistory(params, { customer_id: customerId }),
    [customerId],
  );
  return (
    <RecordsTable
      title="Sales history"
      description="Imported Cin7 invoices and credit notes. Archive only: no journals, no stock."
      columns={SALES_COLUMNS}
      load={load}
      rowId={(row, index) => `${row.document_id}-${index}`}
      hideWhenMissing={Boolean(customerId)}
      searchPlaceholder="Search document, product, customer, or SKU"
    />
  );
}

export function PurchaseHistoryTable({ supplierId }: { supplierId?: string }) {
  const load = useCallback(
    (params: ListParams) => listPurchaseHistory(params, { supplier_id: supplierId }),
    [supplierId],
  );
  return (
    <RecordsTable
      title="Purchase history"
      description="Imported Cin7 supplier invoices in their original currency. Amounts need cost access."
      columns={PURCHASE_COLUMNS}
      load={load}
      rowId={(row, index) => `${row.bill_id}-${index}`}
      searchPlaceholder="Search bill, product, or supplier"
    />
  );
}

export function SupplierPricesTable({ supplierId }: { supplierId?: string }) {
  const load = useCallback(
    (params: ListParams) => listSupplierPrices(params, { supplier_id: supplierId }),
    [supplierId],
  );
  return (
    <RecordsTable
      title="Supplier prices"
      description="Cin7 price by supplier. Prices need cost access."
      columns={PRICE_COLUMNS}
      load={load}
      rowId={(row) => row.id}
      searchPlaceholder="Search SKU, product, or supplier SKU"
    />
  );
}
