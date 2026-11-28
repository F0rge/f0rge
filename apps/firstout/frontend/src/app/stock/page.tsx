"use client";

import { Catalog, DocumentExport, Printer } from "@carbon/icons-react";
import { Button, InlineNotification } from "@carbon/react";
import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, useState } from "react";
import { PageLoading } from "@/components/page-loading";
import { RecordWorkspace, type RecordWorkspaceAdapter } from "@/components/record-workspace";
import { useSkuPanel } from "@/components/sku-panel/provider";
import { StaffImage } from "@/components/staff-image";
import { listSuppliers, skuPhotoUrl, type WorkspaceSkuRow } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { catalogueListKeys, listCategories } from "@/lib/catalogue-lists";
import { loadCatalogueSelection } from "@/lib/catalogue-workspace";
import { downloadCsv } from "@/lib/csv";
import { formatQuantity } from "@/lib/quantity";
import { referenceQueries } from "@/lib/queries";
import { workspaceIdentity } from "@/lib/record-workspace";
import { type WorkspaceQuery } from "@/lib/record-workspace-api";
import { readSkuPanel } from "@/lib/sku-panel";
import { printSkuLabels } from "@/lib/sku-label-print";
import { STOCK_ON_HAND_COLUMNS, byLocation, stockOnHandCsv, stockOnHandFilters } from "@/lib/stock-on-hand";
import catalogueStyles from "../catalogue/page.module.css";
import styles from "./page.module.css";

const CONTEXT_KEY = "stock-on-hand";
const quantity = (value: string) => formatQuantity(Number(value));

const RENDER: Record<(typeof STOCK_ON_HAND_COLUMNS)[number]["key"], (item: WorkspaceSkuRow) => string> = {
  name: (item) => item.name,
  category: (item) => item.subcategory ? `${item.category} › ${item.subcategory}` : (item.category ?? "—"),
  on_hand: (item) => quantity(item.on_hand),
  held: (item) => quantity(item.held),
  available: (item) => quantity(item.available),
  on_order: (item) => quantity(item.on_order),
  stock_locations: (item) => byLocation(item, quantity) || "—",
};

function ProductImage({ sku }: { sku: WorkspaceSkuRow }) {
  return <span className={catalogueStyles.image}>
    <Catalog size={24} aria-hidden="true" />
    {(sku.photo_storage_key || sku.gallery_photo_count > 0) && (
      <StaffImage src={skuPhotoUrl(sku.id)} alt="" width={44} height={44} />
    )}
  </span>;
}

function StockOnHandScreen() {
  const params = useSearchParams();
  const panel = useSkuPanel();
  const suppliersQuery = useQuery({ queryKey: ["catalogue", "suppliers"], queryFn: () => listSuppliers() });
  const categoriesQuery = useQuery({ queryKey: catalogueListKeys.categories(), queryFn: () => listCategories() });
  const locationsQuery = useQuery(referenceQueries.locations);
  const categories = categoriesQuery.data?.categories ?? [];
  const filters = stockOnHandFilters({
    categories: categories.map((item) => item.name),
    subcategories: [...new Set(categories.flatMap((item) => item.subcategories.map((sub) => sub.name)))].sort((a, b) => a.localeCompare(b)),
    suppliers: (suppliersQuery.data ?? []).map((item) => ({ value: item.id, label: item.name })),
    // Archived locations too: stock still sitting there matches, as the By location column shows it.
    locations: [...new Set((locationsQuery.data ?? []).map((item) => item.name))],
  });
  const optionsError = suppliersQuery.error || categoriesQuery.error || locationsQuery.error;

  const [actionError, setActionError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const mounted = useRef(true);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);

  const contextLabel = params.get("q") || "Stock on hand";
  const openSkuId = readSkuPanel(params)?.id ?? null;

  async function exportRows(query: WorkspaceQuery, ids?: string[]) {
    const rows = await loadCatalogueSelection<WorkspaceSkuRow>(query, ids);
    if (!mounted.current) return;
    const csv = stockOnHandCsv(rows);
    downloadCsv(ids ? "firstout-stock-on-hand-selected.csv" : "firstout-stock-on-hand.csv", csv.header, csv.rows);
  }
  async function batch(query: WorkspaceQuery, ids: string[], action: "print" | "export") {
    setBusy(true); setActionError(null);
    try {
      if (action === "export") await exportRows(query, ids);
      else {
        const rows = await loadCatalogueSelection<WorkspaceSkuRow>(query, ids);
        if (mounted.current) await printSkuLabels(rows);
      }
    } catch (err) { if (mounted.current) setActionError(err instanceof Error ? err.message : "Could not complete this action."); }
    finally { if (mounted.current) setBusy(false); }
  }

  const adapter: RecordWorkspaceAdapter<WorkspaceSkuRow> = {
    resource: "skus", title: "Stock on hand", singular: "SKU", plural: "products", breadcrumb: "Stock",
    description: "Every SKU's stock in one list: on hand, held, available and on order, by location.", defaultSort: "name",
    columns: STOCK_ON_HAND_COLUMNS.map((column) => ({ ...column, render: RENDER[column.key] })),
    filters, lifecycle: { activeLabel: "Active", archivedLabel: "Archived" },
    actions: [],
    getTitle: (item) => item.name,
    getSubtitle: (item) => <>{item.our_ref} · {item.preferred_supplier_name ?? "No preferred supplier"}{item.is_kit && <> · Kit</>}</>,
    renderAvatar: (item) => <ProductImage sku={item} />,
  };

  return <>
    {actionError && <InlineNotification kind="error" title="Action failed" subtitle={actionError} lowContrast onCloseButtonClick={() => setActionError(null)} />}
    {optionsError && <InlineNotification kind="warning" title="Filter options unavailable" subtitle="Category, supplier or location choices could not be loaded. The stock list still works." lowContrast hideCloseButton />}
    <RecordWorkspace adapter={adapter}
      onExport={(query) => exportRows(query)}
      renderSelectionActions={({ ids, query }) => <>
        <Button kind="ghost" size="sm" renderIcon={Printer} disabled={busy} onClick={() => void batch(query, ids, "print")}>Print labels</Button>
        <Button kind="ghost" size="sm" renderIcon={DocumentExport} disabled={busy} onClick={() => void batch(query, ids, "export")}>Export selected</Button>
      </>}
      openRecord={{
        activeId: openSkuId,
        // The page of rows is what ↑ ↓ step through in the panel.
        onOpen: (item, rows) => panel?.open(item.id, { ids: rows.map((row) => row.id), label: contextLabel, key: CONTEXT_KEY }),
        onPageItems: (rows) => panel?.refreshContext(CONTEXT_KEY, rows.map((row) => row.id), contextLabel),
      }}
    >
      <p className={`cds--type-body-01 ${styles.note}`}>
        Held stock is set aside for open orders and laybys and has already left on hand. Available is what can be sold now.
        Below reorder minimum follows the reorder list, which adds up every location&apos;s balance, so it can differ from On hand
        when a location has gone below zero.
      </p>
    </RecordWorkspace>
  </>;
}

export default function StockOnHandPage() {
  const { user } = useAuth();
  return <Suspense fallback={<PageLoading label="Loading stock on hand…" />}><StockOnHandScreen key={workspaceIdentity(user)} /></Suspense>;
}
