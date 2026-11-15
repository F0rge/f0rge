"use client";

import { ArrowRight, Catalog, DocumentExport, DocumentImport, Printer } from "@carbon/icons-react";
import { Button, InlineNotification, Link, Stack, Tab, TabList, TabPanel, TabPanels, Tabs, Tag } from "@carbon/react";
import JsBarcode from "jsbarcode";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, useState } from "react";
import { CatalogueSkuEditor } from "@/components/catalogue-sku-editor";
import { RecordDetail, RecordDetails, RecordWorkspace, type RecordWorkspaceAdapter, type WorkspaceField } from "@/components/record-workspace";
import { StaffImage } from "@/components/staff-image";
import { canMutateCatalogue, canViewCostAudit, formatZarAmount, getSkuLeadTimes, listSkuUnitCosts, listSkusPage, listSuppliers, skuPhotoUrl, type Sku, type SkuLeadTimeRow, type Supplier } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { skuCartonCount } from "@/lib/carton-helpers";
import { loadCatalogueSelection } from "@/lib/catalogue-workspace";
import { downloadCsv } from "@/lib/csv";
import { formatObservedMedianLine, skuLeadTimeById } from "@/lib/lead-times";
import { workspaceIdentity } from "@/lib/record-workspace";
import { type WorkspaceQuery } from "@/lib/record-workspace-api";
import { printSkuLabels } from "@/lib/sku-label-print";
import styles from "./page.module.css";

const priceTiers = [
  { key: "stockist_inc_vat", label: "Stockist" },
  { key: "wholesale_inc_vat", label: "Wholesale" },
  { key: "decorator_inc_vat", label: "Decorator" },
  { key: "retail_inc_vat", label: "Retail" },
] as const;
const leadDays = (days: number | null) => days === null ? "—" : `${days} days`;
const money = (value: string | null | undefined) => value === null || value === undefined || value === "" ? "—" : formatZarAmount(value);

function ProductImage({ sku }: { sku: Sku }) {
  return <span className={styles.image}>
    <Catalog size={24} aria-hidden="true" />
    {sku.photo_storage_key && <StaffImage src={skuPhotoUrl(sku.id)} alt="" width={44} height={44} />}
  </span>;
}
function ProductBarcode({ value }: { value: string }) {
  const ref = useRef<SVGSVGElement>(null);
  useEffect(() => {
    if (!ref.current) return;
    try { JsBarcode(ref.current, value, { format: "CODE128", displayValue: false, width: 1.25, height: 38, margin: 0 }); }
    catch { ref.current.replaceChildren(); }
  }, [value]);
  return <div className={styles.barcode}><svg ref={ref} aria-hidden="true" /><code>{value || "—"}</code></div>;
}
function CatalogueScreen() {
  const { user } = useAuth();
  const router = useRouter();
  const params = useSearchParams();
  const allowed = canMutateCatalogue(user);
  const canViewCost = canViewCostAudit(user);
  const [refreshKey, refresh] = useState(0);
  const [metadataReload, reloadMetadata] = useState(0);
  const [editing, setEditing] = useState<Sku | null>(null);
  const [categories, setCategories] = useState<string[]>([]);
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [metadataReady, setMetadataReady] = useState(false);
  const [metadataError, setMetadataError] = useState<string | null>(null);
  const [leadTimes, setLeadTimes] = useState<SkuLeadTimeRow[]>([]);
  const [costs, setCosts] = useState<Map<string, string>>(new Map());
  const [costState, setCostState] = useState<"loading" | "ready" | "failed">(canViewCost ? "loading" : "ready");
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
  useEffect(() => {
    let cancelled = false;
    void Promise.all([listSuppliers(), listSkusPage({ limit: 1, lifecycle: "all" })])
      .then(([items, page]) => { if (!cancelled) { setSuppliers(items); setCategories(page.categories); setMetadataError(null); setMetadataReady(true); } })
      .catch(() => { if (!cancelled) setMetadataError("Supplier and category options could not be loaded. Existing products remain available; retry before editing."); });
    void getSkuLeadTimes().then((report) => { if (!cancelled) setLeadTimes(report.rows); }).catch(() => { if (!cancelled) setLeadTimes([]); });
    return () => { cancelled = true; };
  }, [metadataReload, refreshKey]);
  useEffect(() => {
    if (!canViewCost) return;
    let cancelled = false;
    void listSkuUnitCosts({ lifecycle: "all" }).then((result) => {
      if (!cancelled) { setCosts(new Map(result.items.flatMap((row) => row.unit_cost_zar === null ? [] : [[row.sku_id, row.unit_cost_zar]]))); setCostState("ready"); }
    }).catch(() => { if (!cancelled) { setCosts(new Map()); setCostState("failed"); } });
    return () => { cancelled = true; };
  }, [canViewCost, refreshKey, metadataReload]);
  const leadById = skuLeadTimeById(leadTimes);
  async function exportCatalogue(query: WorkspaceQuery, ids?: string[]) {
    const rows = await loadCatalogueSelection(query, ids);
    const report = canViewCost ? await listSkuUnitCosts({ lifecycle: "all" }).catch(() => null) : null;
    if (!mounted.current) return;
    const exportCosts = new Map((report?.items ?? []).map((row) => [row.sku_id, row.unit_cost_zar]));
    downloadCsv(ids ? "firstout-catalogue-selected.csv" : "firstout-catalogue.csv", ["Our ref", "Name", "Archived", "Category", "Cartons", "Preferred supplier", "Lead time", "Reorder min", ...(canViewCost ? ["Cost (ZAR)"] : []), "Stockist inc VAT", "Wholesale inc VAT", "Decorator inc VAT", "Retail inc VAT", "Our barcode"], rows.map((sku) => [sku.our_ref, sku.name, sku.is_archived ? "Yes" : "No", sku.category ?? "", String(skuCartonCount(sku)), sku.preferred_supplier_name ?? "", leadDays(sku.lead_time_days), sku.reorder_min === null ? "" : String(sku.reorder_min), ...(canViewCost ? [report === null ? "Unavailable" : (exportCosts.get(sku.id) ?? "")] : []), sku.stockist_inc_vat ?? "", sku.wholesale_inc_vat ?? "", sku.decorator_inc_vat ?? "", sku.retail_inc_vat ?? "", sku.our_barcode]));
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
  const filters: WorkspaceField[] = [
    { key: "category", label: "Category", type: "enum", quick: true, allLabel: "All categories", options: categories.map((value) => ({ value, label: value })) },
    { key: "preferred_supplier_id", label: "Supplier", type: "enum", quick: true, options: suppliers.map((item) => ({ value: item.id, label: item.name })) },
    { key: "name", label: "Product name", type: "text" },
    { key: "our_ref", label: "SKU", type: "text" },
    { key: "our_barcode", label: "Barcode", type: "text" },
    { key: "is_kit", label: "Kit", type: "boolean" },
    { key: "is_sellable", label: "Sellable", type: "boolean" },
  ];
  const adapter: RecordWorkspaceAdapter<Sku> = {
    resource: "skus", title: "Catalogue", singular: "SKU", plural: "products", breadcrumb: "Catalogue management",
    description: "Find products, manage pricing and print barcode labels.", defaultSort: "name",
    columns: [
      { key: "name", label: "Product / SKU", render: (item) => item.name, sortable: true },
      { key: "category", label: "Category", render: (item) => item.category ?? "—", sortable: true },
      { key: "retail_inc_vat", label: "Retail price", render: (item) => money(item.retail_inc_vat), numeric: true, sortable: true },
    ], filters, lifecycle: { activeLabel: "Active", archivedLabel: "Archived" },
    actions: allowed ? [{ key: "archive", label: "Archive" }, { key: "restore", label: "Restore" }] : [],
    getTitle: (item) => item.name,
    getSubtitle: (item) => <>{item.our_ref} · {item.preferred_supplier_name ?? "No preferred supplier"}{item.is_kit && <> · Kit</>}</>,
    renderAvatar: (item) => <ProductImage sku={item} />,
    canEdit: (item) => !item.is_archived && metadataReady && !metadataError,
  };
  return <>
    {(actionError || success) && <InlineNotification kind={actionError ? "error" : "success"} title={actionError ? "Action failed" : "SKU updated"} subtitle={actionError ?? success ?? ""} lowContrast onCloseButtonClick={() => { setActionError(null); setSuccess(null); }} />}
    {metadataError && <InlineNotification kind="warning" title="Catalogue options unavailable" subtitle={metadataError} lowContrast hideCloseButton />}
    {costState === "failed" && canViewCost && <InlineNotification kind="warning" title="Costs unavailable" subtitle="Products are shown without unit costs." lowContrast hideCloseButton />}
    {(metadataError || costState === "failed") && <Button kind="ghost" size="sm" onClick={() => reloadMetadata((value) => value + 1)}>Retry catalogue options and costs</Button>}
    <RecordWorkspace adapter={adapter} refreshKey={refreshKey}
      onCreate={allowed ? () => router.push("/catalogue/new") : undefined} createLabel="New SKU"
      onEdit={allowed ? (item) => setEditing(item) : undefined}
      onExport={exportCatalogue}
      headerActions={allowed ? <Button kind="tertiary" renderIcon={DocumentImport} onClick={() => router.push("/import")}>Import</Button> : undefined}
      renderSelectionActions={({ ids, query }) => <><Button kind="ghost" size="sm" renderIcon={Printer} disabled={batchBusy} onClick={() => void batchAction(query, ids, "print")}>Print labels</Button><Button kind="ghost" size="sm" renderIcon={DocumentExport} disabled={batchBusy} onClick={() => void batchAction(query, ids, "export")}>Export selected</Button></>}
      renderDetails={(sku) => <Stack gap={5}>
        {sku.is_archived && <InlineNotification kind="info" title="Archived SKU" subtitle="Restore before editing, selling or adding to a new order or kit. Stock and history remain; existing work and returns can finish. Restoring keeps the previous sales setting and does not publish online." lowContrast hideCloseButton />}
        <Tabs key={sku.id}><TabList aria-label="Product detail sections"><Tab>Overview</Tab><Tab>Pricing</Tab></TabList><TabPanels>
          <TabPanel><Stack gap={5}>
            <RecordDetails><RecordDetail label="Retail price (incl. VAT)">{money(sku.retail_inc_vat)}</RecordDetail><RecordDetail label="Sales setting"><Tag type="gray" size="sm">{sku.is_sellable ? "Sellable" : "Not for sale"}</Tag></RecordDetail>{canViewCost && <RecordDetail label="Unit cost">{costState === "loading" ? "Loading…" : costState === "failed" ? "Unavailable" : money(costs.get(sku.id))}</RecordDetail>}</RecordDetails>
            <RecordDetails><RecordDetail label="Preferred supplier">{sku.preferred_supplier_name}</RecordDetail><RecordDetail label="Supplier ref">{sku.supplier_ref}</RecordDetail><RecordDetail label="Planned lead time">{leadDays(sku.lead_time_days)}</RecordDetail><RecordDetail label="Observed lead time">{formatObservedMedianLine(leadById.get(sku.id))}</RecordDetail><RecordDetail label="Cartons">{skuCartonCount(sku)}</RecordDetail><RecordDetail label="Reorder minimum">{sku.reorder_min}</RecordDetail></RecordDetails>
            <ProductBarcode value={sku.our_barcode} />
          </Stack></TabPanel>
          <TabPanel><RecordDetails>{priceTiers.map((tier) => <RecordDetail key={tier.key} label={`${tier.label} (incl. VAT)`}>{money(sku[tier.key])}</RecordDetail>)}</RecordDetails></TabPanel>
        </TabPanels></Tabs>
        <Link href={`/catalogue/${sku.id}`} renderIcon={ArrowRight}>Open full SKU details</Link>
        <Button kind="tertiary" size="sm" renderIcon={Printer} onClick={() => { void printSkuLabels([sku]).catch((err: unknown) => setActionError(err instanceof Error ? err.message : "Could not print label.")); }}>Print label</Button>
      </Stack>}
    />
    {editing && allowed && !editing.is_archived && metadataReady && !metadataError && <CatalogueSkuEditor key={editing.id} sku={editing} suppliers={suppliers} categories={categories} unitCost={canViewCost ? (costs.get(editing.id) ?? null) : undefined} costLoading={costState === "loading"} onClose={() => setEditing(null)} onSaved={(updated) => { setSuccess(`${updated.name} has been saved.`); refresh((value) => value + 1); }} />}
  </>;
}
export default function CataloguePage() {
  const { user } = useAuth();
  return <Suspense fallback={<p>Loading catalogue…</p>}><CatalogueScreen key={workspaceIdentity(user)} /></Suspense>;
}
