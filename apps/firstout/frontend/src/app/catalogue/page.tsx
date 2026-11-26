"use client";

import { PageLoading } from "@/components/page-loading";
import { Catalog, DocumentExport, DocumentImport, Printer } from "@carbon/icons-react";
import { Button, InlineNotification } from "@carbon/react";
import { useRouter, useSearchParams } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import { CatalogueSkuEditor } from "@/components/catalogue-sku-editor";
import { RecordWorkspace, type RecordWorkspaceAdapter, type WorkspaceField } from "@/components/record-workspace";
import { useSkuPanel, type SkuEditAction } from "@/components/sku-panel/provider";
import { StaffImage } from "@/components/staff-image";
import { canMutateCatalogue, canViewCostAudit, formatZarAmount, listSkuUnitCosts, listSuppliers, skuPhotoUrl, type Sku, type WorkspaceSkuRow } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { catalogueCsv } from "@/lib/catalogue-export";
import { MATERIAL_FAMILY_LABELS, catalogueListKeys, listCategories, listMaterials, type MaterialFamily } from "@/lib/catalogue-lists";
import { queryKeys } from "@/lib/queries";
import { loadCatalogueSelection } from "@/lib/catalogue-workspace";
import { downloadCsv } from "@/lib/csv";
import { formatQuantity } from "@/lib/quantity";
import { workspaceIdentity } from "@/lib/record-workspace";
import { type WorkspaceQuery } from "@/lib/record-workspace-api";
import { readSkuPanel } from "@/lib/sku-panel";
import { printSkuLabels } from "@/lib/sku-label-print";
import styles from "./page.module.css";

const money = (value: string | null | undefined) => value === null || value === undefined || value === "" ? "—" : formatZarAmount(value);
const CONTEXT_KEY = "catalogue";

function stockQuantity(value: string | null | undefined) {
  return value == null || value === "" ? "—" : formatQuantity(Number(value));
}

function ProductImage({ sku }: { sku: Sku }) {
  return <span className={styles.image}>
    <Catalog size={24} aria-hidden="true" />
    {(sku.photo_storage_key || sku.gallery_photo_count > 0) && (
      <StaffImage src={skuPhotoUrl(sku.id)} alt="" width={44} height={44} />
    )}
  </span>;
}
function CatalogueScreen() {
  const { user } = useAuth();
  const router = useRouter();
  const params = useSearchParams();
  const panel = useSkuPanel();
  const allowed = canMutateCatalogue(user);
  const canViewCost = canViewCostAudit(user);
  const [refreshKey, refresh] = useState(0);
  const [editing, setEditing] = useState<{ sku: Sku; startOnPricing?: boolean } | null>(null);
  const client = useQueryClient();
  const suppliersQuery = useQuery({ queryKey: ["catalogue", "suppliers"], queryFn: () => listSuppliers() });
  const categoriesQuery = useQuery({ queryKey: catalogueListKeys.categories(), queryFn: () => listCategories() });
  const materialsQuery = useQuery({ queryKey: catalogueListKeys.materials(), queryFn: () => listMaterials() });
  const categories = categoriesQuery.data?.categories ?? [];
  const categoryNames = categories.map((item) => item.name);
  const subcategoryNames = [...new Set(categories.flatMap((item) => item.subcategories.map((sub) => sub.name)))].sort((a, b) => a.localeCompare(b));
  const suppliers = suppliersQuery.data ?? [];
  const materials = materialsQuery.data ?? [];
  const metadataReady = Boolean(suppliersQuery.data && categoriesQuery.data);
  const metadataError = suppliersQuery.error || categoriesQuery.error || materialsQuery.error
    ? "Supplier, category or material options could not be loaded. Existing products remain available; retry before editing."
    : null;
  const unitCosts = useQuery({
    queryKey: ["catalogue", "unit-costs"],
    queryFn: async () => {
      const result = await listSkuUnitCosts({ lifecycle: "all" });
      return new Map<string, string>(result.items.flatMap((row) => row.unit_cost_zar === null ? [] : [[row.sku_id, row.unit_cost_zar]]));
    },
    enabled: canViewCost,
  });
  const costs = (!unitCosts.error && unitCosts.data) || new Map<string, string>();
  const costState: "loading" | "ready" | "failed" = !canViewCost ? "ready" : unitCosts.error ? "failed" : unitCosts.data ? "ready" : "loading";
  const reloadMetadata = () => {
    void client.invalidateQueries({ queryKey: ["catalogue"] });
    void client.invalidateQueries({ queryKey: catalogueListKeys.categories() });
    void client.invalidateQueries({ queryKey: catalogueListKeys.materials() });
  };
  const [actionError, setActionError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [batchBusy, setBatchBusy] = useState(false);
  const mounted = useRef(true);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  useEffect(() => {
    if (params.get("new") === "1") { router.replace("/catalogue/new"); return; }
    if (params.has("barcode") && !params.has("q")) {
      const next = new URLSearchParams(params); next.set("q", params.get("barcode")?.trim() ?? ""); next.delete("barcode");
      router.replace(`/catalogue?${next}`, { scroll: false });
    }
  }, [params, router]);

  // Until per-card editing lands, the panel's Edit SKU / Edit price open the existing editor modal here.
  const editReady = allowed && metadataReady && !metadataError;
  const setEditAction = panel?.setEditAction;
  const editAction = useCallback<SkuEditAction>((sku, options) => setEditing({ sku, startOnPricing: options.pricing }), []);
  useEffect(() => {
    if (!setEditAction || !editReady) return;
    setEditAction(editAction);
    return () => setEditAction(null);
  }, [setEditAction, editReady, editAction]);

  const contextLabel = params.get("q") || "Catalogue";
  const openSkuId = readSkuPanel(params)?.id ?? null;

  async function exportCatalogue(query: WorkspaceQuery, ids?: string[]) {
    const rows = await loadCatalogueSelection(query, ids);
    const report = canViewCost ? await listSkuUnitCosts({ lifecycle: "all" }).catch(() => null) : null;
    if (!mounted.current) return;
    const exportCosts = canViewCost ? (report ? new Map(report.items.map((row) => [row.sku_id, row.unit_cost_zar])) : null) : undefined;
    const csv = catalogueCsv(rows, exportCosts);
    downloadCsv(ids ? "firstout-catalogue-selected.csv" : "firstout-catalogue.csv", csv.header, csv.rows);
  }
  async function batchAction(query: WorkspaceQuery, ids: string[], action: "print" | "export") {
    setBatchBusy(true); setActionError(null);
    try {
      if (action === "export") await exportCatalogue(query, ids);
      else {
        const rows = await loadCatalogueSelection(query, ids);
        if (mounted.current) await printSkuLabels(rows);
      }
    } catch (err) { if (mounted.current) setActionError(err instanceof Error ? err.message : "Could not complete this action."); }
    finally { if (mounted.current) setBatchBusy(false); }
  }
  const option = (value: string) => ({ value, label: value });
  const filters: WorkspaceField[] = [
    { key: "category", label: "Category", type: "enum", quick: true, allLabel: "All categories", options: categoryNames.map(option) },
    { key: "preferred_supplier_id", label: "Supplier", type: "enum", quick: true, options: suppliers.map((item) => ({ value: item.id, label: item.name })) },
    { key: "subcategory", label: "Sub-category", type: "enum", options: subcategoryNames.map(option) },
    { key: "material", label: "Material", type: "enum", options: materials.map((item) => option(item.name)) },
    { key: "material_family", label: "Material family", type: "enum", options: (Object.keys(MATERIAL_FAMILY_LABELS) as MaterialFamily[]).map((value) => ({ value, label: MATERIAL_FAMILY_LABELS[value] })) },
    { key: "do_not_reorder", label: "Do not reorder", type: "boolean" },
    { key: "name", label: "Product name", type: "text" },
    { key: "our_ref", label: "SKU", type: "text" },
    { key: "our_barcode", label: "Barcode", type: "text" },
    { key: "on_hand", label: "On hand", type: "number" },
    { key: "retail_inc_vat", label: "Retail price (incl. VAT)", type: "number" },
    { key: "is_kit", label: "Kit", type: "boolean" },
    { key: "is_sellable", label: "Sellable", type: "boolean" },
  ];
  const adapter: RecordWorkspaceAdapter<WorkspaceSkuRow> = {
    resource: "skus", title: "Catalogue", singular: "SKU", plural: "products", breadcrumb: "Catalogue management",
    description: "Find products, manage pricing and print barcode labels.", defaultSort: "name",
    columns: [
      { key: "name", label: "Product / SKU", render: (item) => item.name, sortable: true },
      { key: "category", label: "Category", render: (item) => item.subcategory ? `${item.category} › ${item.subcategory}` : (item.category ?? "—"), sortable: true },
      { key: "on_hand", label: "On hand", render: (item) => stockQuantity(item.on_hand), numeric: true, sortable: true },
      { key: "retail_inc_vat", label: "Retail price", render: (item) => money(item.retail_inc_vat), numeric: true, sortable: true },
    ], filters, lifecycle: { activeLabel: "Active", archivedLabel: "Archived" },
    actions: allowed ? [{ key: "archive", label: "Archive" }, { key: "restore", label: "Restore" }] : [],
    getTitle: (item) => item.name,
    getSubtitle: (item) => <>{item.our_ref} · {item.preferred_supplier_name ?? "No preferred supplier"}{item.is_kit && <> · Kit</>}</>,
    renderAvatar: (item) => <ProductImage sku={item} />,
  };
  return <>
    {(actionError || success) && <InlineNotification kind={actionError ? "error" : "success"} title={actionError ? "Action failed" : "SKU updated"} subtitle={actionError ?? success ?? ""} lowContrast onCloseButtonClick={() => { setActionError(null); setSuccess(null); }} />}
    {metadataError && <InlineNotification kind="warning" title="Catalogue options unavailable" subtitle={metadataError} lowContrast hideCloseButton />}
    {costState === "failed" && canViewCost && <InlineNotification kind="warning" title="Costs unavailable" subtitle="Products are exported without unit costs." lowContrast hideCloseButton />}
    {(metadataError || costState === "failed") && <Button kind="ghost" size="sm" onClick={reloadMetadata}>Retry catalogue options and costs</Button>}
    <RecordWorkspace adapter={adapter} refreshKey={refreshKey}
      onCreate={allowed ? () => router.push("/catalogue/new") : undefined} createLabel="New SKU"
      onExport={exportCatalogue}
      headerActions={allowed ? <>
        <Button kind="tertiary" renderIcon={DocumentImport} onClick={() => router.push("/import")}>Import</Button>
        {user?.role === "owner" && <Button kind="tertiary" onClick={() => router.push("/catalogue/curated")}>DasKasas catalogue import</Button>}
      </> : undefined}
      renderSelectionActions={({ ids, query }) => <><Button kind="ghost" size="sm" renderIcon={Printer} disabled={batchBusy} onClick={() => void batchAction(query, ids, "print")}>Print labels</Button><Button kind="ghost" size="sm" renderIcon={DocumentExport} disabled={batchBusy} onClick={() => void batchAction(query, ids, "export")}>Export selected</Button></>}
      openRecord={{
        activeId: openSkuId,
        // The page of rows is what ↑ ↓ step through in the panel.
        onOpen: (item, rows) => panel?.open(item.id, { ids: rows.map((row) => row.id), label: contextLabel, key: CONTEXT_KEY }),
        onPageItems: (rows) => panel?.refreshContext(CONTEXT_KEY, rows.map((row) => row.id), contextLabel),
      }}
    />
    {editing && allowed && !editing.sku.is_archived && metadataReady && !metadataError && (
      <CatalogueSkuEditor
        key={editing.sku.id}
        sku={editing.sku}
        startOnPricing={editing.startOnPricing}
        suppliers={suppliers}
        categories={categoryNames}
        unitCost={canViewCost ? (costs.get(editing.sku.id) ?? null) : undefined}
        costLoading={costState === "loading"}
        onClose={() => setEditing(null)}
        onSaved={(updated) => {
          setSuccess(`${updated.name} has been saved.`);
          refresh((value) => value + 1);
          reloadMetadata();
          void client.invalidateQueries({ queryKey: queryKeys.skus });
          void client.invalidateQueries({ queryKey: catalogueListKeys.skuOverview(updated.id) });
        }}
      />
    )}
  </>;
}
export default function CataloguePage() {
  const { user } = useAuth();
  return <Suspense fallback={<PageLoading label="Loading catalogue…" />}><CatalogueScreen key={workspaceIdentity(user)} /></Suspense>;
}
