"use client";

import { Suspense, useDeferredValue, useEffect, useState } from "react";
import {
  Add,
  CheckmarkFilled,
  Delivery,
  Document,
  Purchase,
} from "@carbon/icons-react";
import {
  Button,
  ClickableTile,
  InlineNotification,
  Pagination,
  Select,
  SelectItem,
  SkeletonText,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableHeader,
  TableRow,
  TableToolbar,
  TableToolbarContent,
  TableToolbarSearch,
  Tag,
  Tile,
} from "@carbon/react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import { PageLoading } from "@/components/page-loading";
import { PurchaseOrderComposer } from "@/components/purchase-orders/composer";
import {
  SelectedOrder,
  orderDate,
  statusPresentation,
} from "@/components/purchase-orders/selected-order";
import styles from "@/components/purchase-orders/purchase-orders.module.css";
import {
  canRaisePo,
  listPurchaseOrders,
  PO_STATUS_LABELS,
  type PurchaseOrder,
  type PurchaseOrderListItem,
  type PurchaseOrderStatus,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { workspaceIdentity } from "@/lib/record-workspace";

type StatusFilter = "all" | PurchaseOrderStatus;
const statuses: PurchaseOrderStatus[] = [
  "pending_approval",
  "rejected",
  "open",
  "on_water",
  "landed",
  "received",
];
const activeStatuses: PurchaseOrderStatus[] = [
  "pending_approval",
  "open",
  "on_water",
  "landed",
];

type Counts = Record<
  "pending_approval" | "open" | "on_water" | "landed",
  number
>;
function OrderOverview({
  refresh,
  onFilter,
}: {
  refresh: number;
  onFilter: (status: StatusFilter) => void;
}) {
  const [counts, setCounts] = useState<Counts | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    let active = true;
    async function load() {
      setError(null);
      try {
        const pages = await Promise.all(
          activeStatuses.map((status) =>
            listPurchaseOrders({ status, limit: 1 }),
          ),
        );
        if (active)
          setCounts({
            pending_approval: pages[0].total,
            open: pages[1].total,
            on_water: pages[2].total,
            landed: pages[3].total,
          });
      } catch (reason) {
        if (active)
          setError(
            reason instanceof Error
              ? reason.message
              : "Could not load order totals.",
          );
      }
    }
    void load();
    return () => {
      active = false;
    };
  }, [refresh, retry]);
  const cards: {
    label: string;
    value: number | undefined;
    detail: string;
    status: PurchaseOrderStatus;
    icon: typeof Purchase;
  }[] = [
    {
      label: "Open orders",
      value: counts?.open,
      detail: "Open supplier orders",
      status: "open",
      icon: Purchase,
    },
    {
      label: "Pending approval",
      value: counts?.pending_approval,
      detail: "Orders with pending status",
      status: "pending_approval",
      icon: Document,
    },
    {
      label: "On water",
      value: counts?.on_water,
      detail: "Shipping stage",
      status: "on_water",
      icon: Delivery,
    },
    {
      label: "Landed",
      value: counts?.landed,
      detail: "Arrival stage",
      status: "landed",
      icon: CheckmarkFilled,
    },
  ];
  return (
    <div
      className={`firstout-loading-motion ${styles.stack}`}
      aria-busy={!counts && !error}
    >
      {!counts && !error && (
        <span className="firstout-sr-only" role="status">
          Loading purchase order status totals…
        </span>
      )}
      {error && (
        <div className={styles.between}>
          <InlineNotification
            kind="warning"
            lowContrast
            title="Order totals unavailable"
            subtitle={error}
            hideCloseButton
          />
          <Button
            kind="ghost"
            size="sm"
            onClick={() => setRetry((value) => value + 1)}
          >
            Retry totals
          </Button>
        </div>
      )}
      <div className={styles.metrics}>
        {cards.map((card) => {
          const content = (
            <div className={styles.smallStack}>
              <div className={styles.between}>
                <p className="cds--type-body-01">{card.label}</p>
                <span className="firstout-content-icon">
                  <card.icon size={20} />
                </span>
              </div>
              {error ? (
                <p className="cds--type-heading-05">—</p>
              ) : card.value == null ? (
                <SkeletonText heading width="40%" />
              ) : (
                <p className="cds--type-heading-05">
                  {card.value.toLocaleString("en-ZA")}
                </p>
              )}
              <p className="cds--type-label-01">{card.detail}</p>
            </div>
          );
          return (
            <div
              key={card.label}
              className={`firstout-section-accent firstout-tone-${statusPresentation(card.status).tone} ${styles.metric}`}
            >
              <ClickableTile
                role="button"
                aria-label={`Show ${PO_STATUS_LABELS[card.status].toLowerCase()} purchase orders`}
                onClick={() => onFilter(card.status)}
              >
                {content}
              </ClickableTile>
            </div>
          );
        })}
      </div>
      <p className="cds--type-helper-text-01">
        Status totals include imported history. Imported orders remain
        read-only.
      </p>
    </div>
  );
}

export default function PurchaseOrdersPage() {
  const { user, loading } = useAuth();
  if (loading)
    return (
      <PageLoading kind="purchase-orders" label="Loading purchase orders…" />
    );
  if (!user) return null;
  return (
    <Suspense
      fallback={
        <PageLoading kind="purchase-orders" label="Loading purchase orders…" />
      }
    >
      <PurchaseOrdersWorkspace
        key={workspaceIdentity(user)}
        canRaise={canRaisePo(user)}
      />
    </Suspense>
  );
}
function PurchaseOrdersWorkspace({ canRaise }: { canRaise: boolean }) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const createRequested = searchParams.get("new") === "1";
  const [orders, setOrders] = useState<PurchaseOrderListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [total, setTotal] = useState(0);
  const [status, setStatus] = useState<StatusFilter>("all");
  const [needsSkus, setNeedsSkus] = useState(false);
  const [query, setQuery] = useState("");
  const deferredQuery = useDeferredValue(query);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [refresh, setRefresh] = useState(0);
  useEffect(() => {
    let active = true;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const response = await listPurchaseOrders({
          limit: pageSize,
          offset: (page - 1) * pageSize,
          status: status === "all" ? undefined : status,
          needs_skus: needsSkus,
          q: deferredQuery,
        });
        if (!active) return;
        setOrders(response.items);
        setTotal(response.total);
        setSelectedId((current) =>
          response.items.some((order) => order.id === current)
            ? current
            : response.items[0]?.id || null,
        );
      } catch (reason) {
        if (active) {
          setError(
            reason instanceof Error
              ? reason.message
              : "Could not load purchase orders.",
          );
          setOrders([]);
          setTotal(0);
          setSelectedId(null);
        }
      } finally {
        if (active) setLoading(false);
      }
    }
    void load();
    return () => {
      active = false;
    };
  }, [page, pageSize, status, needsSkus, deferredQuery, refresh]);
  function filter(next: StatusFilter) {
    setStatus(next);
    setQuery("");
    setNeedsSkus(false);
    setPage(1);
  }
  function closeComposer() {
    setCreateOpen(false);
    if (createRequested) {
      const params = new URLSearchParams(searchParams.toString());
      params.delete("new");
      router.replace(`${pathname}${params.size ? `?${params}` : ""}`, {
        scroll: false,
      });
    }
  }
  function created(order: PurchaseOrder) {
    setSuccess(
      order.status === "pending_approval"
        ? `Purchase order ${order.po_number} is waiting for owner approval.`
        : `Purchase order ${order.po_number} created.`,
    );
    setStatus("all");
    setQuery("");
    setNeedsSkus(false);
    setPage(1);
    setSelectedId(order.id);
    setRefresh((value) => value + 1);
  }
  return (
    <div className={styles.stack}>
      <div className="firstout-page-header">
        <div className={styles.smallStack}>
          <h1 className="cds--type-heading-05">Purchase orders</h1>
          <p className="cds--type-body-01">
            Track supplier orders from approval to stock receipt.
          </p>
        </div>
        {canRaise && (
          <Button
            renderIcon={Add}
            onClick={() => {
              setSuccess(null);
              setCreateOpen(true);
            }}
          >
            New purchase order
          </Button>
        )}
      </div>
      {createRequested && !canRaise && (
        <InlineNotification
          kind="error"
          lowContrast
          title="Permission required"
          subtitle="You do not have permission to raise purchase orders."
          onCloseButtonClick={closeComposer}
        />
      )}
      {success && (
        <InlineNotification
          kind="success"
          lowContrast
          title="Created"
          subtitle={success}
          onCloseButtonClick={() => setSuccess(null)}
        />
      )}
      <OrderOverview refresh={refresh} onFilter={filter} />
      {error && (
        <div className={styles.stack}>
          <InlineNotification
            kind="error"
            lowContrast
            title="Purchase orders unavailable"
            subtitle={error}
            hideCloseButton
          />
          <Button
            kind="tertiary"
            onClick={() => setRefresh((value) => value + 1)}
          >
            Try again
          </Button>
        </div>
      )}
      <div className={styles.layout}>
        <section className="firstout-section-accent firstout-tone-info">
          <TableContainer
            title="Purchase orders"
            description="Searchable orders and imported history"
          >
            <TableToolbar>
              <TableToolbarContent>
                <TableToolbarSearch
                  expanded
                  persistent
                  labelText="Search purchase orders"
                  placeholder="Search PO number, supplier or reference"
                  value={query}
                  onChange={(event) => {
                    setQuery(
                      typeof event === "string" ? event : event.target.value,
                    );
                    setPage(1);
                  }}
                  onClear={() => {
                    setQuery("");
                    setPage(1);
                  }}
                />
              </TableToolbarContent>
            </TableToolbar>
            <div className={styles.filters}>
              <div className={styles.filter}>
                <Select
                  id="po-status-filter"
                  labelText="Status"
                  value={status}
                  onChange={(event) => {
                    setStatus(
                      statuses.find((item) => item === event.target.value) ||
                        "all",
                    );
                    setPage(1);
                  }}
                >
                  <SelectItem value="all" text="All orders" />
                  {statuses.map((item) => (
                    <SelectItem
                      key={item}
                      value={item}
                      text={PO_STATUS_LABELS[item]}
                    />
                  ))}
                </Select>
              </div>
              <div className={styles.filter}>
                <Select
                  id="po-needs-skus-filter"
                  labelText="Needs SKUs"
                  value={needsSkus ? "yes" : "all"}
                  onChange={(event) => {
                    setNeedsSkus(event.target.value === "yes");
                    setPage(1);
                  }}
                >
                  <SelectItem value="all" text="All" />
                  <SelectItem value="yes" text="Needs SKUs" />
                </Select>
              </div>
            </div>
            {loading ? (
              <PageLoading kind="table" label="Loading purchase order list…" />
            ) : orders.length ? (
              <div className={styles.tableScroll}>
                <Table aria-label="Purchase orders" size="lg">
                  <TableHead>
                    <TableRow>
                      <TableHeader>Purchase order</TableHeader>
                      <TableHeader>Supplier</TableHeader>
                      <TableHeader>Status</TableHeader>
                      <TableHeader className={styles.numeric}>
                        Lines
                      </TableHeader>
                      <TableHeader>Ordered / created</TableHeader>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {orders.map((order) => (
                      <TableRow
                        key={order.id}
                        isSelected={selectedId === order.id}
                        onClick={() => setSelectedId(order.id)}
                      >
                        <TableCell>
                          <Button
                            kind="ghost"
                            size="sm"
                            aria-label={`Select purchase order ${order.po_number}`}
                            aria-pressed={selectedId === order.id}
                            onClick={() => setSelectedId(order.id)}
                          >
                            {order.po_number}
                          </Button>
                          {order.supplier_ref && (
                            <p className="cds--type-label-01">
                              {order.supplier_ref}
                            </p>
                          )}
                        </TableCell>
                        <TableCell>{order.supplier_name}</TableCell>
                        <TableCell>
                          <Tag type={statusPresentation(order.status).tag}>
                            {PO_STATUS_LABELS[order.status]}
                          </Tag>
                          {order.is_archive ? (
                            <Tag type="gray">Imported history</Tag>
                          ) : order.needs_sku_count > 0 ? (
                            <Tag type="warm-gray">
                              {order.needs_sku_count} need SKUs
                            </Tag>
                          ) : null}
                        </TableCell>
                        <TableCell className={styles.numeric}>
                          {order.line_count}
                        </TableCell>
                        <TableCell>
                          {orderDate(order.ordered_at || order.created_at)}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            ) : (
              !error && (
                <div className={`${styles.empty} ${styles.stack}`}>
                  <h2 className="cds--type-heading-03">
                    No matching purchase orders
                  </h2>
                  <p className="cds--type-body-01">
                    {query || status !== "all" || needsSkus
                      ? "Try another search or clear the filters."
                      : "Create a purchase order to start ordering from a supplier."}
                  </p>
                  {(query || status !== "all" || needsSkus) && (
                    <Button kind="ghost" onClick={() => filter("all")}>
                      Clear filters
                    </Button>
                  )}
                </div>
              )
            )}
            <Pagination
              page={page}
              pageSize={pageSize}
              pageSizes={[10, 25, 50]}
              totalItems={total}
              onChange={({ page: nextPage, pageSize: nextSize }) => {
                setPage(nextSize === pageSize ? nextPage : 1);
                setPageSize(nextSize);
              }}
              backwardText="Previous page"
              forwardText="Next page"
              itemsPerPageText="Orders per page:"
            />
          </TableContainer>
        </section>
        {selectedId ? (
          <SelectedOrder key={`${selectedId}:${refresh}`} id={selectedId} />
        ) : (
          <Tile>
            <p className="cds--type-body-01">
              Select a purchase order to review its progress and available
              actions.
            </p>
          </Tile>
        )}
      </div>
      <PurchaseOrderComposer
        open={canRaise && (createOpen || createRequested)}
        onClose={closeComposer}
        onCreated={created}
      />
    </div>
  );
}
