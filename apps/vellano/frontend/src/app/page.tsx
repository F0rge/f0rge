"use client";

import {
  Button,
  Column,
  Grid,
  InlineNotification,
  Loading,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableHeader,
  TableRow,
  Tile,
} from "@carbon/react";
import { Add, DocumentImport } from "@carbon/icons-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import {
  ApiError,
  getHomeSummary,
  type HomeAttentionItem,
  type HomeAttentionKind,
  type HomeSummary,
} from "@/lib/api";

function formatZar(value: string, currency: string): string {
  const amount = Number(value);
  if (Number.isNaN(amount)) {
    return value;
  }
  return `${amount.toLocaleString("en-ZA", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })} ${currency}`;
}

function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString("en-ZA");
}

function attentionActionLabel(kind: HomeAttentionKind): string {
  switch (kind) {
    case "low_stock":
      return "Order";
    case "stocktake":
      return "Resume";
    case "returns":
      return "Process";
    case "layby":
      return "View";
    case "bank":
      return "Reconcile";
  }
}

function AttentionAction({
  item,
  onNavigate,
}: {
  item: HomeAttentionItem;
  onNavigate: (href: string) => void;
}) {
  return (
    <Button kind="ghost" size="sm" onClick={() => onNavigate(item.href)}>
      {attentionActionLabel(item.kind)}
    </Button>
  );
}

export default function HomePage() {
  const router = useRouter();
  const [summary, setSummary] = useState<HomeSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getHomeSummary()
      .then((data) => {
        if (!cancelled) {
          setSummary(data);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof ApiError ? err.message : "Failed to load home summary");
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <Stack gap={6}>
      <div>
        <h1 className="cds--type-productive-heading-04">Home</h1>
        <p className="cds--type-body-01">
          Stock cockpit — overview of operations, inventory, and laybys.
        </p>
      </div>

      <div className="vellano-home-actions">
        <Button kind="primary" renderIcon={Add} onClick={() => router.push("/catalogue?new=1")}>
          New stock
        </Button>
        <Button kind="secondary" onClick={() => router.push("/stocktakes")}>
          Stocktake
        </Button>
        <Button kind="secondary" onClick={() => router.push("/adjustments")}>
          Stock adjustment
        </Button>
        <Button
          kind="secondary"
          renderIcon={DocumentImport}
          onClick={() => router.push("/import")}
        >
          Import CSV
        </Button>
        <Button kind="secondary" onClick={() => router.push("/laybys")}>
          New layby
        </Button>
        <Button kind="secondary" onClick={() => router.push("/returns")}>
          Process return
        </Button>
      </div>

      {loading ? <Loading withOverlay={false} description="Loading summary…" /> : null}
      {error ? (
        <InlineNotification kind="error" title="Home summary" subtitle={error} hideCloseButton />
      ) : null}

      {summary ? (
        <>
          <Grid condensed fullWidth>
            <Column lg={5} md={4} sm={4}>
              <Tile className="vellano-home-tile">
                <h2 className="cds--type-productive-heading-03">On order</h2>
                <p className="cds--type-body-01 vellano-home-metric">
                  {summary.on_order_qty.toLocaleString("en-ZA")} units
                </p>
                <p className="cds--type-helper-text-01">
                  {formatZar(summary.on_order_value_zar, summary.home_currency)} estimated
                </p>
              </Tile>
            </Column>
            <Column lg={5} md={4} sm={4}>
              <Tile className="vellano-home-tile">
                <h2 className="cds--type-productive-heading-03">On hand</h2>
                <p className="cds--type-body-01 vellano-home-metric">
                  {summary.on_hand_qty.toLocaleString("en-ZA")} units
                </p>
                <p className="cds--type-helper-text-01">
                  {formatZar(summary.on_hand_value_zar, summary.home_currency)} at landed cost
                </p>
              </Tile>
            </Column>
            <Column lg={5} md={4} sm={4}>
              <Tile className="vellano-home-tile">
                <h2 className="cds--type-productive-heading-03">Aged stock value</h2>
                <p className="cds--type-body-01 vellano-home-metric">
                  {formatZar(summary.aged_stock_value_zar, summary.home_currency)}
                </p>
                <p className="cds--type-helper-text-01">&gt; 180 days</p>
              </Tile>
            </Column>
            <Column lg={5} md={4} sm={4}>
              <Tile className="vellano-home-tile">
                <h2 className="cds--type-productive-heading-03">Open laybys</h2>
                <p className="cds--type-body-01 vellano-home-metric">
                  {summary.open_laybys_count.toLocaleString("en-ZA")} active
                </p>
                <p className="cds--type-helper-text-01">
                  {formatZar(summary.open_laybys_balance_zar, summary.home_currency)} balance
                </p>
              </Tile>
            </Column>
            <Column lg={5} md={4} sm={4}>
              <Tile className="vellano-home-tile">
                <h2 className="cds--type-productive-heading-03">Low-stock SKUs</h2>
                <p
                  className={`cds--type-body-01 vellano-home-metric${
                    summary.low_stock_count > 0 ? " cds--text-error" : ""
                  }`}
                >
                  {summary.low_stock_count.toLocaleString("en-ZA")} items
                </p>
                <p className="cds--type-helper-text-01">Below reorder point</p>
              </Tile>
            </Column>
            <Column lg={5} md={4} sm={4}>
              <Tile className="vellano-home-tile">
                <h2 className="cds--type-productive-heading-03">Returns open</h2>
                <p className="cds--type-body-01 vellano-home-metric">
                  {summary.open_returns_count.toLocaleString("en-ZA")} pending
                </p>
                <p className="cds--type-helper-text-01">Requires processing</p>
              </Tile>
            </Column>
          </Grid>

          <Grid condensed fullWidth>
            <Column lg={8} md={4} sm={4}>
              <h2 className="cds--type-productive-heading-03">Needs attention</h2>
              <TableContainer>
                <Table>
                  <TableHead>
                    <TableRow>
                      <TableHeader>Item / Task</TableHeader>
                      <TableHeader>Status</TableHeader>
                      <TableHeader>Action</TableHeader>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {summary.needs_attention.length === 0 ? (
                      <TableRow>
                        <TableCell colSpan={3}>Nothing needs attention</TableCell>
                      </TableRow>
                    ) : (
                      summary.needs_attention.map((item, index) => (
                        <TableRow key={`${item.kind}-${item.href}-${index}`}>
                          <TableCell>
                            <div className="cds--type-body-compact-01">{item.title}</div>
                            <div className="cds--type-helper-text-01">{item.detail}</div>
                          </TableCell>
                          <TableCell>{item.status}</TableCell>
                          <TableCell>
                            <AttentionAction item={item} onNavigate={router.push} />
                          </TableCell>
                        </TableRow>
                      ))
                    )}
                  </TableBody>
                </Table>
              </TableContainer>
            </Column>
            <Column lg={8} md={4} sm={4}>
              <h2 className="cds--type-productive-heading-03">Recent movements</h2>
              <TableContainer>
                <Table>
                  <TableHead>
                    <TableRow>
                      <TableHeader>Type</TableHeader>
                      <TableHeader>Reference</TableHeader>
                      <TableHeader>Date</TableHeader>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {summary.recent_movements.length === 0 ? (
                      <TableRow>
                        <TableCell colSpan={3}>No recent movements</TableCell>
                      </TableRow>
                    ) : (
                      summary.recent_movements.map((movement, index) => (
                        <TableRow key={`${movement.source}-${movement.created_at}-${index}`}>
                          <TableCell>{movement.source}</TableCell>
                          <TableCell>
                            <div className="cds--type-body-compact-01">{movement.title}</div>
                            <div className="cds--type-helper-text-01">{movement.detail}</div>
                          </TableCell>
                          <TableCell>{formatDateTime(movement.created_at)}</TableCell>
                        </TableRow>
                      ))
                    )}
                  </TableBody>
                </Table>
              </TableContainer>
            </Column>
          </Grid>
        </>
      ) : null}
    </Stack>
  );
}
