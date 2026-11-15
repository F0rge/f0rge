"use client";

import {
  Button,
  ClickableTile,
  InlineNotification,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableHeader,
  TableRow,
  Tag,
  Tile,
} from "@carbon/react";
import {
  ArrowRight,
  Catalog,
  Delivery,
  Home,
  InventoryManagement,
  Money,
  Purchase,
  Receipt,
} from "@carbon/icons-react";
import { useRouter } from "next/navigation";
import {
  useEffect,
  useState,
  type KeyboardEvent,
  type MouseEvent,
} from "react";

import { PageLoading } from "@/components/page-loading";
import {
  ApiError,
  can,
  canRaisePo,
  canReceive,
  canUseTill,
  canViewCostAudit,
  getHomeSummary,
  type HomeAttentionItem,
  type HomeAttentionKind,
  type HomeSummary,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { formatQuantity } from "@/lib/quantity";
import styles from "./page.module.css";

function formatZar(value: string, currency: string): string {
  const amount = Number(value);
  if (!Number.isFinite(amount)) return value;
  return `${amount.toLocaleString("en-ZA", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ${currency}`;
}

function formatRelativeTime(iso: string): string {
  const then = new Date(iso).getTime();
  if (!Number.isFinite(then)) return iso;
  const minutes = Math.round((Date.now() - then) / 60000);
  if (minutes < 1) return "Just now";
  if (minutes < 60) return `${minutes} min${minutes === 1 ? "" : "s"} ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours} hour${hours === 1 ? "" : "s"} ago`;
  const days = Math.round(hours / 24);
  if (days === 1) return "Yesterday";
  return days < 7 ? `${days} days ago` : new Date(iso).toLocaleString("en-ZA");
}

const attentionActions: Record<
  HomeAttentionKind,
  { label: string; permission?: string }
> = {
  low_stock: { label: "Review stock" },
  stocktake: { label: "Resume count", permission: "stock.receive" },
  returns: { label: "Process return", permission: "sales.returns" },
  layby: { label: "Review laybys" },
  bank: { label: "Reconcile", permission: "books.mutate" },
};

function AttentionStatus({ item }: { item: HomeAttentionItem }) {
  return (
    <Tag type={item.kind === "stocktake" ? "blue" : "warm-gray"}>
      {item.status}
    </Tag>
  );
}

export default function HomePage() {
  const router = useRouter();
  const { user } = useAuth();
  const [summary, setSummary] = useState<HomeSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  const canViewCost = canViewCostAudit(user);
  const firstName = user?.display_name?.trim().split(/\s+/)[0];

  function followShortcut(
    event: MouseEvent<HTMLAnchorElement> | KeyboardEvent<HTMLAnchorElement>,
    href: string,
  ) {
    if (
      ("button" in event && event.button !== 0) ||
      event.metaKey ||
      event.ctrlKey ||
      event.shiftKey ||
      event.altKey
    )
      return;
    event.preventDefault();
    router.push(href);
  }

  useEffect(() => {
    let cancelled = false;
    getHomeSummary()
      .then((data) => {
        if (!cancelled) setSummary(data);
      })
      .catch((err: unknown) => {
        if (!cancelled)
          setError(
            err instanceof ApiError
              ? err.message
              : "Failed to load home summary",
          );
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [attempt]);

  const shortcuts = [
    {
      title: "New sale",
      detail: "Start a customer sale",
      icon: Money,
      href: "/till",
      allowed: canUseTill(user),
    },
    {
      title: "Purchase order",
      detail: "Build a supplier order",
      icon: Purchase,
      href: "/purchase-orders?new=1",
      allowed: canRaisePo(user),
    },
    {
      title: "Receive stock",
      detail: "Review stock ready to receive",
      icon: Delivery,
      href: "/receive",
      allowed: canReceive(user),
    },
  ].filter((item) => item.allowed);

  const metrics = summary
    ? [
        {
          label: "Stock on hand",
          value: formatQuantity(summary.on_hand_qty),
          unit: "units",
          detail: canViewCost
            ? `${formatZar(summary.on_hand_value_zar, summary.home_currency)} landed cost`
            : "Across your locations",
          icon: InventoryManagement,
          attention: false,
        },
        {
          label: "On order",
          value: formatQuantity(summary.on_order_qty),
          unit: "units",
          detail: canViewCost
            ? `${formatZar(summary.on_order_value_zar, summary.home_currency)} estimated`
            : "Awaiting stock receipt",
          icon: Delivery,
          attention: false,
        },
        {
          label: "Low-stock products",
          value: summary.low_stock_count.toLocaleString("en-ZA"),
          unit: "products",
          detail: "Only 1–2 units remaining",
          icon: Catalog,
          attention: summary.low_stock_count > 0,
        },
        {
          label: "Open laybys",
          value: summary.open_laybys_count.toLocaleString("en-ZA"),
          unit: "active",
          detail: `${formatZar(summary.open_laybys_balance_zar, summary.home_currency)} outstanding`,
          icon: Receipt,
          attention: false,
        },
      ]
    : [];

  return (
    <div className={styles.page}>
      <header className={styles.heading}>
        <div className={styles.stackSmall}>
          <h1 className="cds--type-heading-05">Home</h1>
          <p className="cds--type-body-01">
            Your daily overview. See what needs attention and keep things
            moving.
          </p>
        </div>
        {canUseTill(user) && (
          <Button renderIcon={ArrowRight} onClick={() => router.push("/till")}>
            Open till
          </Button>
        )}
      </header>

      {loading ? (
        <PageLoading kind="home" label="Loading your overview" />
      ) : null}
      {error ? (
        <div className={styles.stackSmall}>
          <InlineNotification
            kind="error"
            title="Home summary"
            subtitle={error}
            hideCloseButton
          />
          <Button
            kind="tertiary"
            onClick={() => {
              setError(null);
              setLoading(true);
              setAttempt((value) => value + 1);
            }}
          >
            Try again
          </Button>
        </div>
      ) : null}

      {summary && !loading && (
        <>
          <div className={styles.intro}>
            <section
              className={`firstout-page-intro firstout-tone-info ${styles.welcome}`}
            >
              <span className="firstout-content-icon firstout-tone-info">
                <Home size={24} />
              </span>
              <p className="cds--type-label-01">TODAY’S BRIEFING</p>
              <h2 className="cds--type-heading-05">
                Hello{firstName ? `, ${firstName}` : ""}.
              </h2>
              <p className="cds--type-body-01">
                {summary.low_stock_count.toLocaleString("en-ZA")} low-stock
                products and {summary.open_laybys_count.toLocaleString("en-ZA")}{" "}
                open laybys. Review your stock and customer commitments in one
                place.
              </p>
              <Button
                kind="ghost"
                renderIcon={ArrowRight}
                onClick={() =>
                  document
                    .getElementById("home-needs-attention")
                    ?.scrollIntoView({
                      behavior: window.matchMedia(
                        "(prefers-reduced-motion: reduce)",
                      ).matches
                        ? "auto"
                        : "smooth",
                      block: "center",
                    })
                }
              >
                Review priorities
              </Button>
            </section>
            {shortcuts.length > 0 && (
              <section className={styles.stack}>
                <h2 className="cds--type-heading-03">Make your next move</h2>
                <div className={styles.shortcuts}>
                  {shortcuts.map((item) => (
                    <div
                      className="firstout-section-accent firstout-tone-info"
                      key={item.href}
                    >
                      <ClickableTile
                        href={item.href}
                        aria-label={item.title}
                        onClick={(event) => followShortcut(event, item.href)}
                      >
                        <div className={styles.shortcutContent}>
                          <span className="firstout-content-icon firstout-tone-info">
                            <item.icon size={24} />
                          </span>
                          <h3 className="cds--type-heading-compact-01">
                            {item.title}
                          </h3>
                          <p className="cds--type-body-01">{item.detail}</p>
                          <ArrowRight size={20} />
                        </div>
                      </ClickableTile>
                    </div>
                  ))}
                </div>
              </section>
            )}
          </div>

          <div className={styles.metrics}>
            {metrics.map((metric) => (
              <div
                className={`firstout-section-accent firstout-tone-${metric.attention ? "attention" : "info"}`}
                key={metric.label}
              >
                <Tile>
                  <div className={styles.stackSmall}>
                    <div className={styles.row}>
                      <p className="cds--type-body-01">{metric.label}</p>
                      <span
                        className={`firstout-content-icon firstout-tone-${metric.attention ? "attention" : "info"}`}
                      >
                        <metric.icon size={20} />
                      </span>
                    </div>
                    <p className="cds--type-heading-05">
                      {metric.value}{" "}
                      <span className="cds--type-body-01">{metric.unit}</span>
                    </p>
                    <p className="cds--type-label-01">{metric.detail}</p>
                  </div>
                </Tile>
              </div>
            ))}
          </div>

          <div className={styles.tables}>
            <section id="home-needs-attention" className={styles.tableSection}>
              <TableContainer
                title="Needs attention"
                description="A short list to keep your day moving."
              >
                <div className={styles.tableScroll}>
                  <Table aria-label="Needs attention" size="lg">
                    <TableHead>
                      <TableRow>
                        <TableHeader>Task</TableHeader>
                        <TableHeader>Status</TableHeader>
                        <TableHeader>Action</TableHeader>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {summary.needs_attention.length === 0 ? (
                        <TableRow>
                          <TableCell colSpan={3}>
                            Nothing needs attention
                          </TableCell>
                        </TableRow>
                      ) : (
                        summary.needs_attention.map((item, index) => (
                          <TableRow key={`${item.kind}-${item.href}-${index}`}>
                            <TableCell>
                              <p className="cds--type-body-01">{item.title}</p>
                              <p className="cds--type-label-01">
                                {item.detail}
                              </p>
                            </TableCell>
                            <TableCell>
                              <AttentionStatus item={item} />
                            </TableCell>
                            <TableCell>
                              <Button
                                kind="ghost"
                                size="sm"
                                renderIcon={ArrowRight}
                                onClick={() => router.push(item.href)}
                              >
                                {!attentionActions[item.kind].permission ||
                                can(
                                  user,
                                  attentionActions[item.kind].permission!,
                                )
                                  ? attentionActions[item.kind].label
                                  : "View details"}
                              </Button>
                            </TableCell>
                          </TableRow>
                        ))
                      )}
                    </TableBody>
                  </Table>
                </div>
              </TableContainer>
            </section>
            <section className={styles.tableSection}>
              <TableContainer
                title="Recent movements"
                description="Latest recorded stock activity."
              >
                <div className={styles.tableScroll}>
                  <Table aria-label="Recent stock movements" size="lg">
                    <TableHead>
                      <TableRow>
                        <TableHeader>Movement</TableHeader>
                        <TableHeader>Reference</TableHeader>
                        <TableHeader>When</TableHeader>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {summary.recent_movements.length === 0 ? (
                        <TableRow>
                          <TableCell colSpan={3}>No recent movements</TableCell>
                        </TableRow>
                      ) : (
                        summary.recent_movements.map((movement, index) => (
                          <TableRow
                            key={`${movement.source}-${movement.created_at}-${index}`}
                          >
                            <TableCell>
                              <Tag
                                type={
                                  movement.source === "receive" ||
                                  movement.source === "land"
                                    ? "green"
                                    : "gray"
                                }
                              >
                                {movement.source}
                              </Tag>
                            </TableCell>
                            <TableCell>
                              <p className="cds--type-body-01">
                                {movement.title}
                              </p>
                              <p className="cds--type-label-01">
                                {movement.detail}
                              </p>
                            </TableCell>
                            <TableCell>
                              {formatRelativeTime(movement.created_at)}
                            </TableCell>
                          </TableRow>
                        ))
                      )}
                    </TableBody>
                  </Table>
                </div>
              </TableContainer>
            </section>
          </div>
          <div className={styles.followUp}>
            {canViewCost && (
              <Tile>
                <div className={styles.stackSmall}>
                  <h2 className="cds--type-heading-compact-01">
                    Aged stock value
                  </h2>
                  <p className="cds--type-heading-03">
                    {formatZar(
                      summary.aged_stock_value_zar,
                      summary.home_currency,
                    )}
                  </p>
                  <p className="cds--type-label-01">
                    Stock held for more than 180 days
                  </p>
                </div>
              </Tile>
            )}
            <Tile>
              <div className={styles.stackSmall}>
                <h2 className="cds--type-heading-compact-01">Open returns</h2>
                <p className="cds--type-heading-03">
                  {summary.open_returns_count.toLocaleString("en-ZA")}
                </p>
                <p className="cds--type-label-01">Awaiting processing</p>
              </div>
            </Tile>
          </div>
        </>
      )}
      {!loading && !error && !summary && (
        <Tile>
          <p className="cds--type-body-01">
            Your stock overview will appear when records are available.
          </p>
        </Tile>
      )}
    </div>
  );
}
