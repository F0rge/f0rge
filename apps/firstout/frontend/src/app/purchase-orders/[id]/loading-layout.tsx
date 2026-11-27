"use client";

import { Button, SkeletonText, Stack, TableContainer } from "@carbon/react";
import Link from "next/link";
import { LoadingRegion, LoadingTableRows } from "@/components/page-loading";
import styles from "@/components/purchase-orders/purchase-orders.module.css";

export const purchaseOrderLineColumns = [
  "Our ref",
  "Supplier code",
  "Description",
  "Name",
  "Finish",
  "Qty",
  "Factory unit",
  "Unit cost ZAR",
];
export const landingBillColumns = ["Kind", "Invoice number", "Amount", "Currency"];

export function PurchaseOrderDetailLoading() {
  return (
    <LoadingRegion label="Loading purchase order…">
      <Stack gap={6}>
        <Stack gap={3}>
          <Button as={Link} href="/purchase-orders" kind="ghost" size="sm">
            ← Back to purchase orders
          </Button>
          <h1 className="firstout-sr-only">Purchase order</h1>
          <div aria-hidden="true">
            <SkeletonText heading width="14rem" />
            <SkeletonText width="18rem" />
            <SkeletonText width="16rem" />
          </div>
        </Stack>
        <TableContainer title="Lines" description="PO line items">
          <div className={styles.tableScroll}>
            <LoadingTableRows columns={purchaseOrderLineColumns} rows={2} />
          </div>
        </TableContainer>
        <TableContainer title="Landing bills" description="Factory, freight, and clearance">
          <div className={styles.tableScroll}>
            <LoadingTableRows columns={landingBillColumns} rows={3} />
          </div>
        </TableContainer>
      </Stack>
    </LoadingRegion>
  );
}
