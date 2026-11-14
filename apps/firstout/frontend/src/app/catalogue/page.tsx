"use client";

import {
  Add,
  ArrowRight,
  Barcode,
  Catalog,
  ChevronLeft,
  ChevronRight,
  DocumentExport,
  DocumentImport,
  Edit,
  Printer,
} from "@carbon/icons-react";
import {
  Button,
  Checkbox,
  InlineNotification,
  Search,
  Select,
  SelectItem,
  Tab,
  TabList,
  TabPanel,
  TabPanels,
  Tabs,
  Tag,
} from "@carbon/react";
import JsBarcode from "jsbarcode";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, useState } from "react";

import { CatalogueSkuEditor } from "@/components/catalogue-sku-editor";
import { StaffImage } from "@/components/staff-image";
import {
  canMutateCatalogue,
  canViewCostAudit,
  formatZarAmount,
  getSkuLeadTimes,
  listSkuUnitCosts,
  listSkus,
  listSkusPage,
  listSuppliers,
  skuPhotoUrl,
  type Sku,
  type SkuLeadTimeRow,
  type Supplier,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { skuCartonCount } from "@/lib/carton-helpers";
import { downloadCsv } from "@/lib/csv";
import { formatObservedMedianLine, skuLeadTimeById } from "@/lib/lead-times";
import { printSkuLabels } from "@/lib/sku-label-print";

import styles from "./page.module.css";

type Query = {
  q: string;
  category: string;
  supplier: string;
  page: number;
  size: number;
};
type Result = {
  key: string;
  items: Sku[];
  total: number;
  categories: string[];
  error: string | null;
};
const priceTiers = [
  { key: "stockist_inc_vat", label: "Stockist" },
  { key: "wholesale_inc_vat", label: "Wholesale" },
  { key: "decorator_inc_vat", label: "Decorator" },
  { key: "retail_inc_vat", label: "Retail" },
] as const;
const leadDays = (days: number | null) =>
  days === null ? "—" : `${days} days`;
const money = (value: string | null | undefined) =>
  value === null || value === undefined || value === ""
    ? "—"
    : formatZarAmount(value);

function ProductImage({ sku, large = false }: { sku: Sku; large?: boolean }) {
  return (
    <span className={`${styles.image} ${large ? styles.imageLarge : ""}`}>
      <Catalog size={large ? 36 : 24} aria-hidden="true" />
      {sku.photo_storage_key && (
        <StaffImage
          src={skuPhotoUrl(sku.id)}
          alt=""
          width={large ? 72 : 44}
          height={large ? 72 : 44}
        />
      )}
    </span>
  );
}

function ProductBarcode({ value }: { value: string }) {
  const ref = useRef<SVGSVGElement>(null);
  useEffect(() => {
    if (!ref.current) return;
    try {
      JsBarcode(ref.current, value, {
        format: "CODE128",
        displayValue: false,
        width: 1.25,
        height: 38,
        margin: 0,
      });
    } catch {
      ref.current.replaceChildren();
    }
  }, [value]);
  return (
    <div className={styles.barcode}>
      <svg ref={ref} aria-hidden="true" />
      <code>{value || "—"}</code>
    </div>
  );
}

function CataloguePageContent({ initialQuery }: { initialQuery: string }) {
  const { user } = useAuth();
  const router = useRouter();
  const canMutate = canMutateCatalogue(user);
  const canViewCost = canViewCostAudit(user);
  const [query, setQuery] = useState<Query>({
    q: initialQuery,
    category: "",
    supplier: "",
    page: 1,
    size: 50,
  });
  const [input, setInput] = useState(initialQuery);
  const [reload, setReload] = useState(0);
  const [metadataReload, setMetadataReload] = useState(0);
  const [result, setResult] = useState<Result | null>(null);
  const [costReload, setCostReload] = useState(0);
  const [costResult, setCostResult] = useState<{
    key: string;
    status: "ready" | "failed";
    costs: Map<string, string>;
  } | null>(null);
  const [suppliers, setSuppliers] = useState<{
    identity: string;
    items: Supplier[];
    error: string | null;
  } | null>(null);
  const [leadTimes, setLeadTimes] = useState<SkuLeadTimeRow[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [activeId, setActiveId] = useState<string | null>(null);
  const [detailTab, setDetailTab] = useState(0);
  const [editing, setEditing] = useState<Sku | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);
  const mounted = useRef(true);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);
  const identity = `${user?.team.id ?? ""}:${user?.id ?? ""}`;
  const key = JSON.stringify([identity, canViewCost, query, reload]);
  const costKey = JSON.stringify([key, costReload]);
  const costLoading = canViewCost && costResult?.key !== costKey;
  const costUnavailable =
    canViewCost &&
    costResult?.key === costKey &&
    costResult.status === "failed";
  const unitCosts =
    costResult?.key === costKey && costResult.status === "ready"
      ? costResult.costs
      : new Map<string, string>();
  const ready = result?.key === key && input.trim() === query.q;
  const loading = !ready;
  const skus = ready && !result.error ? result.items : [];
  const total = ready ? result.total : 0;
  const categories = [
    ...new Set([
      ...(query.category ? [query.category] : []),
      ...(result?.categories ?? []),
    ]),
  ];
  const supplierItems = suppliers?.identity === identity ? suppliers.items : [];
  const suppliersReady = suppliers?.identity === identity && !suppliers.error;
  const supplierError =
    suppliers?.identity === identity ? suppliers.error : null;
  const active = skus.find((sku) => sku.id === activeId) ?? skus[0];
  const selectedSkus = skus.filter((sku) => selected.has(sku.id));
  const allSelected = skus.length > 0 && selectedSkus.length === skus.length;
  const leadById = skuLeadTimeById(leadTimes);
  const pageCount = Math.max(1, Math.ceil(total / query.size));

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setQuery((current) =>
        current.q === input.trim()
          ? current
          : { ...current, q: input.trim(), page: 1 },
      );
    }, 250);
    return () => window.clearTimeout(timer);
  }, [input]);

  useEffect(() => {
    if (!user) return;
    let cancelled = false;
    const request = {
      limit: query.size,
      offset: (query.page - 1) * query.size,
      q: query.q,
      category: query.category || undefined,
      preferred_supplier_id: query.supplier || undefined,
    };
    void listSkusPage(request)
      .then((page) => {
        if (cancelled) return;
        const lastPage = Math.max(1, Math.ceil(page.total / query.size));
        if (query.page > lastPage) {
          setQuery((current) => ({ ...current, page: lastPage }));
          return;
        }
        setResult({
          key,
          items: page.items,
          total: page.total,
          categories: page.categories,
          error: null,
        });
      })
      .catch((error: unknown) => {
        if (!cancelled)
          setResult({
            key,
            items: [],
            total: 0,
            categories: [],
            error:
              error instanceof Error
                ? error.message
                : "Could not load the catalogue.",
          });
      });
    return () => {
      cancelled = true;
    };
  }, [canViewCost, key, query, user]);

  useEffect(() => {
    if (!user || !canViewCost) return;
    let cancelled = false;
    const request = {
      limit: query.size,
      offset: (query.page - 1) * query.size,
      q: query.q,
      category: query.category || undefined,
      preferred_supplier_id: query.supplier || undefined,
    };
    void listSkuUnitCosts(request)
      .then((costs) => {
        if (!cancelled)
          setCostResult({
            key: costKey,
            status: "ready",
            costs: new Map(
              costs.items.flatMap((entry) =>
                entry.unit_cost_zar === null
                  ? []
                  : [[entry.sku_id, entry.unit_cost_zar]],
              ),
            ),
          });
      })
      .catch(() => {
        if (!cancelled)
          setCostResult({ key: costKey, status: "failed", costs: new Map() });
      });
    return () => {
      cancelled = true;
    };
  }, [canViewCost, costKey, query, user]);

  useEffect(() => {
    if (!user) return;
    let cancelled = false;
    void listSuppliers()
      .then((items) => {
        if (!cancelled) setSuppliers({ identity, items, error: null });
      })
      .catch(() => {
        if (!cancelled)
          setSuppliers({
            identity,
            items: [],
            error:
              "Suppliers could not be loaded. Supplier filtering and editing are temporarily unavailable.",
          });
      });
    void getSkuLeadTimes()
      .then((report) => {
        if (!cancelled) setLeadTimes(report.rows);
      })
      .catch(() => {
        if (!cancelled) setLeadTimes([]);
      });
    return () => {
      cancelled = true;
    };
  }, [identity, metadataReload, user]);

  function changeQuery(change: Partial<Query>) {
    setSelected(new Set());
    setActiveId(null);
    setActionError(null);
    setQuery((current) => ({ ...current, ...change }));
  }

  function resetFilters() {
    setInput("");
    changeQuery({ q: "", category: "", supplier: "", page: 1 });
  }

  async function exportCsv(onlySelected = false) {
    if (exporting || !ready) return;
    setExporting(true);
    setActionError(null);
    const filters = {
      q: query.q,
      category: query.category || undefined,
      preferred_supplier_id: query.supplier || undefined,
    };
    try {
      const matching = onlySelected ? selectedSkus : await listSkus(filters);
      let costs = unitCosts;
      let unavailable = costUnavailable;
      if (canViewCost && (!onlySelected || costLoading)) {
        const costResult = await listSkuUnitCosts(
          onlySelected
            ? {
                ...filters,
                limit: query.size,
                offset: (query.page - 1) * query.size,
              }
            : filters,
        ).catch(() => null);
        unavailable = costResult === null;
        costs = new Map(
          (costResult?.items ?? []).flatMap((entry) =>
            entry.unit_cost_zar === null
              ? []
              : [[entry.sku_id, entry.unit_cost_zar]],
          ),
        );
      }
      if (!mounted.current) return;
      downloadCsv(
        onlySelected
          ? "firstout-catalogue-selected.csv"
          : "firstout-catalogue.csv",
        [
          "Our ref",
          "Name",
          "Category",
          "Cartons",
          "Preferred supplier",
          "Lead time",
          "Reorder min",
          ...(canViewCost ? ["Cost (ZAR)"] : []),
          "Stockist inc VAT",
          "Wholesale inc VAT",
          "Decorator inc VAT",
          "Retail inc VAT",
          "Our barcode",
        ],
        matching.map((sku) => [
          sku.our_ref,
          sku.name,
          sku.category ?? "",
          String(skuCartonCount(sku)),
          sku.preferred_supplier_name ?? "",
          leadDays(sku.lead_time_days),
          sku.reorder_min === null ? "" : String(sku.reorder_min),
          ...(canViewCost
            ? [unavailable ? "Unavailable" : (costs.get(sku.id) ?? "")]
            : []),
          sku.stockist_inc_vat ?? "",
          sku.wholesale_inc_vat ?? "",
          sku.decorator_inc_vat ?? "",
          sku.retail_inc_vat ?? "",
          sku.our_barcode,
        ]),
      );
    } catch (error: unknown) {
      if (mounted.current)
        setActionError(
          error instanceof Error
            ? error.message
            : "Could not export the catalogue.",
        );
    } finally {
      if (mounted.current) setExporting(false);
    }
  }

  function print(skusToPrint: Sku[]) {
    void printSkuLabels(skusToPrint).catch((error: unknown) => {
      if (mounted.current)
        setActionError(
          error instanceof Error ? error.message : "Could not print labels.",
        );
    });
  }

  return (
    <div className={styles.page}>
      <div className={styles.breadcrumb}>
        <span>Catalogue management</span>
        <ChevronRight size={12} aria-hidden="true" />
        <span>Products</span>
      </div>
      <header className={styles.header}>
        <div>
          <h1>Catalogue</h1>
          <p>Find products, manage pricing and print barcode labels.</p>
        </div>
        <div className={styles.actions}>
          <Button
            kind="ghost"
            renderIcon={DocumentExport}
            disabled={loading || total === 0 || exporting}
            onClick={() => {
              void exportCsv();
            }}
          >
            {exporting ? "Exporting…" : "Export CSV"}
          </Button>
          {canMutate && (
            <>
              <Button
                kind="tertiary"
                renderIcon={DocumentImport}
                onClick={() => router.push("/import")}
              >
                Import
              </Button>
              <Button
                renderIcon={Add}
                onClick={() => router.push("/catalogue/new")}
              >
                New SKU
              </Button>
            </>
          )}
        </div>
      </header>
      {(success || actionError) && (
        <InlineNotification
          kind={actionError ? "error" : "success"}
          lowContrast
          title={actionError ? "Action failed" : "SKU updated"}
          subtitle={actionError ?? success ?? ""}
          onCloseButtonClick={() => {
            setSuccess(null);
            setActionError(null);
          }}
        />
      )}
      {supplierError && (
        <div className={styles.warning}>
          <InlineNotification
            kind="warning"
            lowContrast
            hideCloseButton
            title="Suppliers unavailable"
            subtitle={supplierError}
          />
          <Button
            kind="ghost"
            size="sm"
            onClick={() => setMetadataReload((current) => current + 1)}
          >
            Retry suppliers
          </Button>
        </div>
      )}
      {ready && costUnavailable && (
        <div className={styles.warning}>
          <InlineNotification
            kind="warning"
            lowContrast
            hideCloseButton
            title="Costs unavailable"
            subtitle="Products are shown without unit costs."
          />
          <Button
            kind="ghost"
            size="sm"
            onClick={() => setCostReload((current) => current + 1)}
          >
            Retry costs
          </Button>
        </div>
      )}
      <div className={styles.filters}>
        <div className={styles.search}>
          <Search
            id="catalogue-search"
            size="lg"
            labelText="Search catalogue"
            placeholder="Search by product name, SKU or barcode"
            value={input}
            onChange={(event) => {
              setInput(event.target.value);
              setSelected(new Set());
              setActiveId(null);
            }}
          />
        </div>
        <Select
          id="catalogue-category"
          labelText="Category"
          value={query.category}
          onChange={(event) =>
            changeQuery({ category: event.target.value, page: 1 })
          }
        >
          <SelectItem value="" text="All categories" />
          {categories.map((category) => (
            <SelectItem key={category} value={category} text={category} />
          ))}
        </Select>
        <Select
          id="catalogue-supplier"
          labelText="Supplier"
          value={query.supplier}
          disabled={!suppliersReady}
          onChange={(event) =>
            changeQuery({ supplier: event.target.value, page: 1 })
          }
        >
          <SelectItem
            value=""
            text={supplierError ? "Suppliers unavailable" : "All suppliers"}
          />
          {supplierItems.map((supplier) => (
            <SelectItem
              key={supplier.id}
              value={supplier.id}
              text={supplier.name}
            />
          ))}
        </Select>
        <Button
          kind="ghost"
          size="md"
          disabled={!input && !query.category && !query.supplier}
          onClick={resetFilters}
        >
          Reset filters
        </Button>
      </div>
      <div className={styles.layout}>
        <section className={styles.list} aria-label="Catalogue products">
          <div className={styles.listHeading}>
            <div>
              <h2>{query.category || "All products"}</h2>
              <p aria-live="polite">
                {loading
                  ? "Loading products…"
                  : `${total} ${total === 1 ? "product" : "products"}`}
              </p>
            </div>
            <Select
              id="catalogue-page-size"
              labelText="Products per page"
              size="sm"
              inline
              value={query.size}
              onChange={(event) =>
                changeQuery({ size: Number(event.target.value), page: 1 })
              }
            >
              <SelectItem value={50} text="50" />
              <SelectItem value={100} text="100" />
            </Select>
          </div>
          {selectedSkus.length > 0 && (
            <div className={styles.selection}>
              <strong>{selectedSkus.length} selected</strong>
              <Button
                kind="ghost"
                size="md"
                renderIcon={Printer}
                onClick={() => print(selectedSkus)}
              >
                Print labels
              </Button>
              <Button
                kind="ghost"
                size="md"
                renderIcon={DocumentExport}
                disabled={exporting}
                onClick={() => {
                  void exportCsv(true);
                }}
              >
                Export selected
              </Button>
              <button onClick={() => setSelected(new Set())}>Cancel</button>
            </div>
          )}
          <div
            className={styles.tableScroll}
            key={`${query.page}:${query.size}`}
            aria-busy={loading}
          >
            <table className={styles.table}>
              <thead>
                <tr>
                  <th className={styles.check}>
                    <Checkbox
                      id="catalogue-select-all"
                      labelText="Select all products on this page"
                      hideLabel
                      disabled={loading || skus.length === 0}
                      checked={allSelected}
                      indeterminate={selectedSkus.length > 0 && !allSelected}
                      onChange={() =>
                        setSelected(
                          allSelected
                            ? new Set()
                            : new Set(skus.map((sku) => sku.id)),
                        )
                      }
                    />
                  </th>
                  <th>Product / SKU</th>
                  <th>Category</th>
                  <th className={styles.numeric}>Retail price</th>
                  <th>
                    <span className={styles.srOnly}>View product</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {skus.map((sku) => (
                  <tr
                    key={sku.id}
                    className={sku.id === active?.id ? styles.active : ""}
                  >
                    <td className={styles.check}>
                      <Checkbox
                        id={`catalogue-select-${sku.id}`}
                        labelText={`Select ${sku.our_ref}`}
                        hideLabel
                        checked={selected.has(sku.id)}
                        onChange={() =>
                          setSelected((current) => {
                            const next = new Set(current);
                            if (next.has(sku.id)) next.delete(sku.id);
                            else next.add(sku.id);
                            return next;
                          })
                        }
                      />
                    </td>
                    <td>
                      <button
                        className={styles.product}
                        aria-pressed={sku.id === active?.id}
                        onClick={() => {
                          setActiveId(sku.id);
                          setDetailTab(0);
                        }}
                      >
                        <ProductImage sku={sku} />
                        <span>
                          <strong>{sku.name}</strong>
                          <small>
                            {sku.our_ref}
                            <span> · </span>
                            {sku.preferred_supplier_name ??
                              "No preferred supplier"}
                          </small>
                        </span>
                        {sku.is_kit && (
                          <Tag type="teal" size="sm">
                            Kit
                          </Tag>
                        )}
                      </button>
                    </td>
                    <td className={styles.category}>{sku.category ?? "—"}</td>
                    <td className={styles.numeric}>
                      {money(sku.retail_inc_vat)}
                    </td>
                    <td className={styles.view}>
                      <button
                        aria-label={`View ${sku.our_ref}`}
                        onClick={() => {
                          setActiveId(sku.id);
                          setDetailTab(0);
                        }}
                      >
                        <ChevronRight size={16} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {loading ? (
              <div className={styles.empty} role="status">
                <p>Loading catalogue…</p>
              </div>
            ) : result.error ? (
              <div className={styles.empty}>
                <h3>Catalogue could not be loaded</h3>
                <p>{result.error}</p>
                <Button
                  kind="tertiary"
                  size="sm"
                  onClick={() => setReload((current) => current + 1)}
                >
                  Retry
                </Button>
              </div>
            ) : skus.length === 0 ? (
              <div className={styles.empty}>
                <Catalog size={32} />
                <h3>
                  {query.q || query.category || query.supplier
                    ? "No products found"
                    : "No products yet"}
                </h3>
                <p>
                  {query.q || query.category || query.supplier
                    ? "Try another search or reset your filters."
                    : "Add a SKU or import your catalogue to get started."}
                </p>
                {query.q || query.category || query.supplier ? (
                  <Button kind="tertiary" size="sm" onClick={resetFilters}>
                    Reset filters
                  </Button>
                ) : (
                  canMutate && (
                    <Button
                      size="sm"
                      renderIcon={Add}
                      onClick={() => router.push("/catalogue/new")}
                    >
                      New SKU
                    </Button>
                  )
                )}
              </div>
            ) : null}
          </div>
          <footer className={styles.pagination}>
            <span aria-live="polite">
              {loading
                ? "Loading…"
                : total
                  ? `${(query.page - 1) * query.size + 1}–${Math.min(query.page * query.size, total)} of ${total} products`
                  : "0 products"}
            </span>
            <span>
              Page {query.page} of {loading ? "—" : pageCount}
            </span>
            <button
              disabled={loading || query.page === 1}
              aria-label="Previous page"
              onClick={() => changeQuery({ page: query.page - 1 })}
            >
              <ChevronLeft size={16} />
            </button>
            <button
              disabled={loading || query.page >= pageCount}
              aria-label="Next page"
              onClick={() => changeQuery({ page: query.page + 1 })}
            >
              <ChevronRight size={16} />
            </button>
          </footer>
        </section>
        <aside className={styles.inspector} aria-label="Product details">
          <div className={styles.inspectorLabel}>
            <span>PRODUCT DETAILS</span>
            {active && (
              <Tag type="gray" size="sm" className={styles.status}>
                Selected
              </Tag>
            )}
          </div>
          {active ? (
            <>
              <div className={styles.identity}>
                <ProductImage sku={active} large />
                <div>
                  <small>{active.our_ref}</small>
                  <h2>{active.name}</h2>
                  <p>{active.category ?? "Uncategorised"}</p>
                </div>
              </div>
              <Tabs
                selectedIndex={detailTab}
                onChange={({ selectedIndex }) => setDetailTab(selectedIndex)}
              >
                <TabList aria-label="Product detail sections">
                  <Tab>Overview</Tab>
                  <Tab>Pricing</Tab>
                </TabList>
                <TabPanels>
                  <TabPanel>
                    <section className={styles.section}>
                      <h3>
                        Prices <span>ZAR · sale prices incl. VAT</span>
                      </h3>
                      <div className={styles.retail}>
                        <span>Retail price</span>
                        <strong>{money(active.retail_inc_vat)}</strong>
                      </div>
                      <div className={styles.prices}>
                        {canViewCost && (
                          <div>
                            <span>Unit cost</span>
                            <strong>
                              {costLoading
                                ? "Loading…"
                                : costUnavailable
                                  ? "Unavailable"
                                  : money(unitCosts.get(active.id))}
                            </strong>
                          </div>
                        )}
                        {priceTiers
                          .filter((tier) => tier.key !== "retail_inc_vat")
                          .map((tier) => (
                            <div key={tier.key}>
                              <span>{tier.label}</span>
                              <strong>{money(active[tier.key])}</strong>
                            </div>
                          ))}
                      </div>
                    </section>
                    <section className={styles.section}>
                      <h3>Procurement</h3>
                      <dl className={styles.procurement}>
                        <div>
                          <dt>Preferred supplier</dt>
                          <dd>{active.preferred_supplier_name ?? "Not set"}</dd>
                        </div>
                        <div>
                          <dt>Supplier ref</dt>
                          <dd>{active.supplier_ref ?? "Not set"}</dd>
                        </div>
                        <div>
                          <dt>Planned lead time</dt>
                          <dd>{leadDays(active.lead_time_days)}</dd>
                        </div>
                        <div>
                          <dt>Cartons</dt>
                          <dd>{skuCartonCount(active)}</dd>
                        </div>
                        <div>
                          <dt>Reorder minimum</dt>
                          <dd>{active.reorder_min ?? "Not set"}</dd>
                        </div>
                      </dl>
                      <p className={styles.observed}>
                        {formatObservedMedianLine(leadById.get(active.id))}
                      </p>
                    </section>
                    <section className={styles.section}>
                      <h3>Our barcode</h3>
                      <ProductBarcode value={active.our_barcode} />
                    </section>
                  </TabPanel>
                  <TabPanel>
                    <section className={styles.section}>
                      <h3>
                        Price tiers <span>ZAR · sale prices incl. VAT</span>
                      </h3>
                      {canViewCost && (
                        <div className={styles.priceRow}>
                          <span>Unit cost</span>
                          <strong>
                            {costLoading
                              ? "Loading…"
                              : costUnavailable
                                ? "Unavailable"
                                : money(unitCosts.get(active.id))}
                          </strong>
                        </div>
                      )}
                      {priceTiers.map((tier) => (
                        <div key={tier.key} className={styles.priceRow}>
                          <span>{tier.label}</span>
                          <strong>{money(active[tier.key])}</strong>
                        </div>
                      ))}
                    </section>
                  </TabPanel>
                </TabPanels>
              </Tabs>
              <button
                className={styles.detailsLink}
                onClick={() => router.push(`/catalogue/${active.id}`)}
              >
                Open full SKU details <ArrowRight size={16} />
              </button>
              <div className={styles.inspectorActions}>
                <Button
                  kind="tertiary"
                  renderIcon={Printer}
                  onClick={() => print([active])}
                >
                  Print label
                </Button>
                {canMutate && (
                  <Button
                    renderIcon={Edit}
                    disabled={!suppliersReady}
                    onClick={() => setEditing(active)}
                  >
                    Edit SKU
                  </Button>
                )}
              </div>
            </>
          ) : (
            <div className={styles.inspectorEmpty}>
              <Barcode size={32} />
              <h3>{loading ? "Loading products" : "No product selected"}</h3>
              <p>
                {loading
                  ? "Product details will appear here."
                  : "Choose a product from the catalogue to view its details."}
              </p>
            </div>
          )}
        </aside>
      </div>
      {editing && canMutate && suppliersReady && (
        <CatalogueSkuEditor
          key={editing.id}
          sku={editing}
          suppliers={supplierItems}
          categories={categories}
          unitCost={
            canViewCost ? (unitCosts.get(editing.id) ?? null) : undefined
          }
          costLoading={costLoading}
          onClose={() => setEditing(null)}
          onSaved={(updated) => {
            setActiveId(updated.id);
            setSelected(new Set());
            setSuccess(`${updated.name} has been saved.`);
            setReload((current) => current + 1);
          }}
        />
      )}
    </div>
  );
}

function CatalogueRoute() {
  const params = useSearchParams();
  const router = useRouter();
  const { user } = useAuth();
  const q = params.get("q")?.trim() ?? params.get("barcode")?.trim() ?? "";
  useEffect(() => {
    if (params.get("new") === "1") router.replace("/catalogue/new");
  }, [params, router]);
  return (
    <CataloguePageContent
      key={`${user?.team.id ?? ""}:${user?.id ?? ""}:${q}`}
      initialQuery={q}
    />
  );
}

export default function CataloguePage() {
  return (
    <Suspense fallback={<p>Loading catalogue…</p>}>
      <CatalogueRoute />
    </Suspense>
  );
}
