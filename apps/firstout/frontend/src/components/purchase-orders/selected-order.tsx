"use client";

import { useQuery } from "@tanstack/react-query";
import { Fragment, useState } from "react";
import { ArrowRight, Document } from "@carbon/icons-react";
import {
  Button,
  InlineNotification,
  ProgressIndicator,
  ProgressStep,
  SkeletonPlaceholder,
  SkeletonText,
  Tag,
  Tile,
} from "@carbon/react";
import { useRouter } from "next/navigation";
import { LoadingRegion } from "@/components/page-loading";
import {
  downloadPackingSheet,
  getPurchaseOrder,
  getSupplier,
  PO_STATUS_LABELS,
  type PurchaseOrderStatus,
} from "@/lib/api";
import { factoryTotal, formatFactoryAmount } from "./composer-state";
import styles from "./purchase-orders.module.css";
import { usePageError } from "@/hooks/use-page-error";

export function statusPresentation(status: PurchaseOrderStatus): {
  tone: string;
  tag: "purple" | "blue" | "green" | "gray" | "red";
} {
  switch (status) {
    case "pending_approval":
      return { tone: "pending", tag: "purple" };
    case "on_water":
      return { tone: "info", tag: "blue" };
    case "landed":
    case "received":
      return { tone: "ready", tag: "green" };
    case "rejected":
      return { tone: "error", tag: "red" };
    default:
      return { tone: "neutral", tag: "gray" };
  }
}
export function orderDate(value: string | null): string {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? value
    : date.toLocaleDateString("en-ZA", {
        day: "numeric",
        month: "short",
        year: "numeric",
      });
}

export function SelectedOrderLoading({ announce = true }: { announce?: boolean }) {
  return (
    <LoadingRegion label="Loading selected purchase order…" announce={announce}>
      <Tile>
        <div className={styles.stack}>
          <div className={styles.between}>
            <div className={styles.smallStack}>
              <p className="cds--type-label-01">SELECTED PURCHASE ORDER</p>
              <SkeletonText heading width="9rem" aria-hidden="true" />
            </div>
            <SkeletonPlaceholder aria-hidden="true" style={{ width: "4.5rem", height: "1.5rem" }} />
          </div>
          <div className={styles.smallStack} aria-hidden="true">
            <SkeletonText heading width="65%" />
            <SkeletonText width="55%" />
          </div>
          <dl className={styles.detailValues}>
            {["Ordered / created", "Order quantity", "Factory total"].map((label) => (
              <Fragment key={label}>
                <dt className="cds--type-label-01">{label}</dt>
                <dd aria-hidden="true"><SkeletonText width="65%" /></dd>
              </Fragment>
            ))}
          </dl>
          <div aria-hidden="true">
            <SkeletonText paragraph lineCount={4} width="45%" />
          </div>
        </div>
      </Tile>
    </LoadingRegion>
  );
}

/** The caller keys this panel by order ID. */
export function SelectedOrder({ id }: { id: string }) {
  const router = useRouter();
  const [downloading, setDownloading] = useState(false);
  const orderQuery = useQuery({
    queryKey: ["purchase-orders", "detail", id],
    queryFn: () => getPurchaseOrder(id),
  });
  const order = orderQuery.data ?? null;
  const supplierQuery = useQuery({
    queryKey: ["suppliers", "detail", order?.supplier_id],
    queryFn: () => getSupplier(order!.supplier_id),
    enabled: Boolean(order && !order.is_archive && order.source_currency_known),
  });
  const currency = supplierQuery.data ? supplierQuery.data.default_currency || "USD" : null;
  const currencyError = supplierQuery.error
    ? supplierQuery.error.message || "Could not load the supplier currency."
    : null;
  const loading = orderQuery.isFetching || supplierQuery.isFetching;
  const { error, setError } = usePageError(orderQuery.error, "Could not load the purchase order.");
  const retry = () => {
    setError(null);
    void orderQuery.refetch();
    if (supplierQuery.isEnabled) void supplierQuery.refetch();
  };
  async function packingSheet() {
    if (!order || order.is_archive || downloading) return;
    setDownloading(true);
    setError(null);
    try {
      await downloadPackingSheet(order.id, order.po_number);
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "Could not download the packing sheet.",
      );
    } finally {
      setDownloading(false);
    }
  }
  if (loading)
    return <SelectedOrderLoading />;
  if (!order)
    return (
      <div className={styles.stack}>
        <InlineNotification
          kind="error"
          lowContrast
          title="Purchase order unavailable"
          subtitle={error || "Could not load this purchase order."}
          hideCloseButton
        />
        <Button kind="tertiary" onClick={retry}>
          Try again
        </Button>
      </div>
    );
  const presentation = statusPresentation(order.status);
  const step = ["open", "on_water", "landed", "received"].indexOf(order.status);
  const total =
    !order.is_archive && order.source_amounts_known
      ? factoryTotal(order.lines)
      : null;
  return (
    <section
      aria-label={`Selected purchase order ${order.po_number}`}
      className={`firstout-section-accent firstout-tone-${presentation.tone}`}
    >
      <Tile>
        <div className={styles.stack}>
          <div className={styles.between}>
            <div className={styles.smallStack}>
              <p className="cds--type-label-01">SELECTED PURCHASE ORDER</p>
              <h2 className="cds--type-heading-03">{order.po_number}</h2>
            </div>
            <Tag type={presentation.tag}>{PO_STATUS_LABELS[order.status]}</Tag>
          </div>
          <div className={styles.smallStack}>
            <h3 className="cds--type-heading-02">{order.supplier_name}</h3>
            <p className="cds--type-body-01">
              Supplier reference · {order.supplier_ref || "Not provided"}
            </p>
          </div>
          {error && (
            <InlineNotification
              kind="error"
              lowContrast
              title="Could not complete action"
              subtitle={error}
              hideCloseButton
            />
          )}
          {currencyError && (
            <div className={styles.smallStack}>
              <InlineNotification
                kind="warning"
                lowContrast
                title="Supplier currency unavailable"
                subtitle={currencyError}
                hideCloseButton
              />
              <Button
                kind="ghost"
                size="sm"
                onClick={retry}
              >
                Retry currency lookup
              </Button>
            </div>
          )}
          <dl className={styles.detailValues}>
            <dt className="cds--type-label-01">Ordered / created</dt>
            <dd className="cds--type-body-01">
              {orderDate(order.ordered_at || order.created_at)}
            </dd>
            <dt className="cds--type-label-01">Order quantity</dt>
            <dd className="cds--type-body-01">
              {order.lines
                .reduce((sum, line) => sum + line.qty, 0)
                .toLocaleString("en-ZA")}{" "}
              units · {order.lines.length} lines
            </dd>
            <dt className="cds--type-label-01">Factory total</dt>
            <dd className="cds--type-body-01">
              {order.is_archive
                ? "See imported source amounts"
                : !order.source_amounts_known
                  ? "Not provided in source"
                  : !order.source_currency_known
                    ? "Currency not provided in source"
                    : formatFactoryAmount(total, currency)}
            </dd>
            {order.on_water_at && (
              <>
                <dt className="cds--type-label-01">On water</dt>
                <dd className="cds--type-body-01">
                  {orderDate(order.on_water_at)}
                </dd>
              </>
            )}
            {order.landed_at && (
              <>
                <dt className="cds--type-label-01">Landed</dt>
                <dd className="cds--type-body-01">
                  {orderDate(order.landed_at)}
                </dd>
              </>
            )}
            {order.received_at && (
              <>
                <dt className="cds--type-label-01">Received</dt>
                <dd className="cds--type-body-01">
                  {orderDate(order.received_at)}
                </dd>
              </>
            )}
          </dl>
          {order.is_archive ? (
            <InlineNotification
              kind="info"
              lowContrast
              title="Imported history"
              subtitle="This order is read-only. Open it to see the original source details and amounts."
              hideCloseButton
            />
          ) : step >= 0 ? (
            <div className={styles.progress}>
              <ProgressIndicator vertical currentIndex={step}>
                {["Open", "On water", "Landed", "Received"].map(
                  (label, index) => (
                    <ProgressStep
                      key={label}
                      label={label}
                      description={label}
                      complete={step > index}
                    />
                  ),
                )}
              </ProgressIndicator>
            </div>
          ) : (
            <InlineNotification
              kind={order.needs_sku_count ? "warning" : "info"}
              lowContrast
              title={
                order.status === "pending_approval"
                  ? "Waiting for approval"
                  : "Order rejected"
              }
              subtitle={
                order.needs_sku_count
                  ? `${order.needs_sku_count} order lines need a SKU before approval.`
                  : "Open the purchase order to review its full details and available actions."
              }
              hideCloseButton
            />
          )}
          {order.notes && (
            <div className={styles.smallStack}>
              <h3 className="cds--type-heading-compact-01">Order notes</h3>
              <p className={`cds--type-body-01 ${styles.note}`}>
                {order.notes}
              </p>
            </div>
          )}
          <div className={styles.detailActions}>
            <Button
              renderIcon={ArrowRight}
              onClick={() =>
                router.push(`/purchase-orders/${encodeURIComponent(order.id)}`)
              }
            >
              {order.is_archive
                ? "View imported history"
                : "Open purchase order"}
            </Button>
            {!order.is_archive && (
              <Button
                kind="tertiary"
                renderIcon={Document}
                disabled={downloading}
                onClick={() => void packingSheet()}
              >
                {downloading ? "Downloading…" : "Packing sheet"}
              </Button>
            )}
          </div>
          {!order.is_archive && (
            <p className="cds--type-helper-text-01">
              Approval, shipping, landed costs and receipt remain available
              inside the purchase order. Stock becomes available only after
              receipt.
            </p>
          )}
        </div>
      </Tile>
    </section>
  );
}
