"use client";

import {
  Button,
  Checkbox,
  DataTable,
  FeatureFlags,
  InlineNotification,
  MenuItem,
  OverflowMenu,
  Stack,
  Tag,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableHeader,
  Pagination,
  TableRow,
  TextInput,
} from "@carbon/react";
import { Barcode, DocumentExport, DocumentImport, Printer } from "@carbon/icons-react";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, useState } from "react";

import {
  canMutateCatalogue,
  canViewCostAudit,
  formatPriceAmount,
  getSkuLeadTimes,
  listSkuUnitCosts,
  listSkus,
  listSkusPage,
  skuPhotoUrl,
  type Sku,
  type SkuLeadTimeRow,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { skuCartonCount } from "@/lib/carton-helpers";
import { downloadCsv } from "@/lib/csv";
import { formatObservedMedianLine, skuLeadTimeById } from "@/lib/lead-times";
import { printSkuLabels } from "@/lib/sku-label-print";

const TABLE_HEADERS = [
  { key: "select", header: "" },
  { key: "product", header: "SKU / Product Name" },
  { key: "category", header: "Category" },
  { key: "cartons", header: "Cartons" },
  { key: "preferred_supplier", header: "Preferred supplier" },
  { key: "lead_time_days", header: "Lead time" },
  { key: "reorder_min", header: "Reorder min" },
  { key: "cost_zar", header: "Cost (ZAR)" },
  { key: "stockist_inc_vat", header: "Stockist Price" },
  { key: "wholesale_inc_vat", header: "Wholesale Price" },
  { key: "decorator_inc_vat", header: "Decorator Price" },
  { key: "retail_inc_vat", header: "Retail Price" },
  { key: "our_barcode", header: "Our barcode" },
  { key: "actions", header: "Actions" },
] as const;

type SkuRow = {
  id: string;
  product: string;
  category: string;
  cartons: string;
  preferred_supplier: string;
  lead_time_days: string;
  reorder_min: string;
  cost_zar: string;
  stockist_inc_vat: string;
  wholesale_inc_vat: string;
  decorator_inc_vat: string;
  retail_inc_vat: string;
  our_barcode: string;
  select: string;
  actions: string;
};

function formatLeadTime(days: number | null | undefined): string {
  if (days === null || days === undefined) {
    return "—";
  }
  return `${days} days`;
}

function formatCatalogueMoney(value: string | null | undefined): string {
  if (!value) {
    return "—";
  }
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) {
    return "—";
  }
  return `R ${formatPriceAmount(parsed)}`;
}

function formatIncVatPrice(value: string | null | undefined): string {
  return formatCatalogueMoney(value);
}

function CataloguePageContent() {
  const { user } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();
  const canMutate = canMutateCatalogue(user);
  const canViewCost = canViewCostAudit(user);
  const urlQuery = searchParams.get("q")?.trim() ?? searchParams.get("barcode")?.trim() ?? "";
  const [skus, setSkus] = useState<Sku[]>([]);
  const [total, setTotal] = useState(0);
  const [categories, setCategories] = useState<string[]>([]);
  const [skuLeadTimes, setSkuLeadTimes] = useState<SkuLeadTimeRow[]>([]);
  const [unitCostBySku, setUnitCostBySku] = useState<Map<string, string>>(new Map());
  const [costUnavailable, setCostUnavailable] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchInput, setSearchInput] = useState(urlQuery);
  const [searchFilter, setSearchFilter] = useState(urlQuery);
  const [categoryFilter, setCategoryFilter] = useState<string | null>(null);
  const [selectedById, setSelectedById] = useState<Map<string, Sku>>(() => new Map());
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const searchTimer = useRef<number | null>(null);
  const [trackedUrlQuery, setTrackedUrlQuery] = useState(urlQuery);
  if (urlQuery !== trackedUrlQuery) {
    setTrackedUrlQuery(urlQuery);
    setSearchInput(urlQuery);
    setSearchFilter(urlQuery);
    setPage(1);
  }

  useEffect(() => {
    if (!user) {
      return;
    }
    let cancelled = false;
    const request = {
      limit: pageSize,
      offset: (page - 1) * pageSize,
      q: searchFilter,
      category: categoryFilter ?? undefined,
    };
    listSkusPage(request)
      .then((skuPage) => {
        if (cancelled) {
          return;
        }
        setSkus(skuPage.items);
        setTotal(skuPage.total);
        setCategories(skuPage.categories);
        setError(null);
        setLoading(false);
        if (!canViewCost) {
          setUnitCostBySku(new Map());
          setCostUnavailable(false);
          return;
        }
        listSkuUnitCosts(request)
          .then((costs) => {
            if (cancelled) {
              return;
            }
            const next = new Map<string, string>();
            for (const entry of costs.items) {
              if (entry.unit_cost_zar) {
                next.set(entry.sku_id, entry.unit_cost_zar);
              }
            }
            setUnitCostBySku(next);
            setCostUnavailable(false);
          })
          .catch(() => {
            if (cancelled) {
              return;
            }
            setUnitCostBySku(new Map());
            setCostUnavailable(true);
          });
      })
      .catch((err: unknown) => {
        if (cancelled) {
          return;
        }
        setError(err instanceof Error ? err.message : "Failed to load catalogue.");
        setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [canViewCost, categoryFilter, page, pageSize, searchFilter, user]);

  useEffect(() => {
    if (!user) {
      return;
    }
    let cancelled = false;
    void getSkuLeadTimes()
      .then((report) => {
        if (!cancelled) {
          setSkuLeadTimes(report.rows);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setSkuLeadTimes([]);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [user]);

  useEffect(() => {
    if (searchParams.get("new") !== "1") {
      return;
    }
    router.replace("/catalogue/new");
  }, [searchParams, router]);

  useEffect(() => {
    return () => {
      if (searchTimer.current !== null) {
        window.clearTimeout(searchTimer.current);
      }
    };
  }, []);

  function onSearchChange(value: string) {
    setSearchInput(value);
    if (searchTimer.current !== null) {
      window.clearTimeout(searchTimer.current);
    }
    searchTimer.current = window.setTimeout(() => {
      const next = value.trim();
      setSearchFilter(next);
      setPage(1);
      setLoading(true);
    }, 250);
  }

  const pagedSkus = skus;

  const allPageSelected = skus.length > 0 && skus.every((sku) => selectedById.has(sku.id));

  const tableHeaders = canViewCost
    ? TABLE_HEADERS
    : TABLE_HEADERS.filter((header) => header.key !== "cost_zar");

  const leadBySku = skuLeadTimeById(skuLeadTimes);

  const rows: SkuRow[] = pagedSkus.map((entry) => ({
    id: entry.id,
    product: entry.id,
    category: entry.category?.trim() || "—",
    cartons: String(skuCartonCount(entry)),
    preferred_supplier: entry.preferred_supplier_name?.trim() || "—",
    lead_time_days: formatLeadTime(entry.lead_time_days),
    reorder_min: entry.reorder_min !== null ? String(entry.reorder_min) : "—",
    cost_zar: costUnavailable
      ? "Unavailable"
      : formatCatalogueMoney(unitCostBySku.get(entry.id) ?? null),
    stockist_inc_vat: formatIncVatPrice(entry.stockist_inc_vat),
    wholesale_inc_vat: formatIncVatPrice(entry.wholesale_inc_vat),
    decorator_inc_vat: formatIncVatPrice(entry.decorator_inc_vat),
    retail_inc_vat: formatIncVatPrice(entry.retail_inc_vat),
    our_barcode: entry.our_barcode,
    select: entry.id,
    actions: entry.id,
  }));

  function toggleSelect(sku: Sku) {
    setSelectedById((prev) => {
      const next = new Map(prev);
      if (next.has(sku.id)) {
        next.delete(sku.id);
      } else {
        next.set(sku.id, sku);
      }
      return next;
    });
  }

  function toggleSelectPage() {
    setSelectedById((prev) => {
      const next = new Map(prev);
      if (allPageSelected) {
        for (const sku of skus) {
          next.delete(sku.id);
        }
      } else {
        for (const sku of skus) {
          next.set(sku.id, sku);
        }
      }
      return next;
    });
  }

  async function handlePrintLabels() {
    try {
      const targetSkus =
        selectedById.size > 0
          ? Array.from(selectedById.values())
          : await listSkus({
              category: categoryFilter ?? undefined,
              q: searchFilter,
            });
      printSkuLabels(targetSkus);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load catalogue.");
    }
  }

  async function handleExport() {
    try {
      const matching = await listSkus({
        category: categoryFilter ?? undefined,
        q: searchFilter,
      });
      let costs = unitCostBySku;
      if (canViewCost) {
        try {
          const costPage = await listSkuUnitCosts({
            category: categoryFilter ?? undefined,
            q: searchFilter,
          });
          costs = new Map();
          for (const entry of costPage.items) {
            if (entry.unit_cost_zar) {
              costs.set(entry.sku_id, entry.unit_cost_zar);
            }
          }
        } catch {
          costs = new Map();
        }
      }
      downloadCsv(
        "firstout-catalogue.csv",
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
          sku.category?.trim() || "",
          String(skuCartonCount(sku)),
          sku.preferred_supplier_name?.trim() || "",
          formatLeadTime(sku.lead_time_days),
          sku.reorder_min !== null ? String(sku.reorder_min) : "",
          ...(canViewCost
            ? [costUnavailable && costs.size === 0 ? "Unavailable" : (costs.get(sku.id) ?? "")]
            : []),
          sku.stockist_inc_vat ?? "",
          sku.wholesale_inc_vat ?? "",
          sku.decorator_inc_vat ?? "",
          sku.retail_inc_vat ?? "",
          sku.our_barcode,
        ]),
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load catalogue.");
    }
  }

  return (
    <Stack gap={6}>
      <div className="firstout-page-header">
        <div>
          <h1 className="cds--type-productive-heading-04">Catalogue</h1>
          <p className="cds--type-body-01">
            Browse products, filter by category, and print barcode labels.
          </p>
        </div>
        <div className="firstout-catalogue-actions">
          <Button
            kind="secondary"
            renderIcon={DocumentExport}
            disabled={total === 0}
            onClick={() => {
              void handleExport();
            }}
          >
            Export CSV
          </Button>
          {canMutate ? (
            <>
              <Button
                kind="secondary"
                renderIcon={DocumentImport}
                onClick={() => router.push("/import")}
              >
                Import
              </Button>
              <Button data-tour="catalogue-new" onClick={() => router.push("/catalogue/new")}>New SKU</Button>
            </>
          ) : null}
        </div>
      </div>

      {error ? (
        <InlineNotification
          kind="error"
          title="Error"
          subtitle={error}
          onCloseButtonClick={() => setError(null)}
          lowContrast
        />
      ) : null}

      {costUnavailable ? (
        <InlineNotification
          kind="warning"
          title="Cost unavailable"
          subtitle="Unit costs could not be loaded. The catalogue is shown without costs."
          hideCloseButton
          lowContrast
        />
      ) : null}

      {loading && skus.length === 0 ? (
        <p className="cds--type-body-01">Loading catalogue…</p>
      ) : error && skus.length === 0 ? null : !loading && total === 0 && !searchFilter && !categoryFilter ? (
        <InlineNotification
          kind="info"
          title="No SKUs"
          subtitle="No catalogue items have been added yet."
          hideCloseButton
          lowContrast
        />
      ) : (
        <div className="firstout-catalogue-panel">
          <div className="firstout-catalogue-toolbar">
            <div className="firstout-catalogue-toolbar__left">
              <TextInput
                id="catalogue-search"
                labelText="Filter SKUs"
                hideLabel
                placeholder="Filter SKUs…"
                value={searchInput}
                onChange={(event) => onSearchChange(event.target.value)}
                size="md"
              />
              <div className="firstout-catalogue-toolbar__divider" aria-hidden />
              <div className="firstout-catalogue-chips" role="group" aria-label="Category filter">
                <Button
                  kind={categoryFilter === null ? "primary" : "ghost"}
                  size="sm"
                  onClick={() => {
                    setCategoryFilter(null);
                    setPage(1);
                    setLoading(true);
                  }}
                >
                  All
                </Button>
                {categories.map((category) => (
                  <Button
                    key={category}
                    kind={categoryFilter === category ? "primary" : "ghost"}
                    size="sm"
                    onClick={() => {
                      setCategoryFilter(category);
                      setPage(1);
                      setLoading(true);
                    }}
                  >
                    {category}
                  </Button>
                ))}
              </div>
            </div>
            <Button kind="ghost" renderIcon={Printer} onClick={handlePrintLabels}>
              Print labels
            </Button>
          </div>

          <DataTable rows={rows} headers={[...tableHeaders]}>
            {({ rows: tableRows, headers, getTableProps, getHeaderProps, getRowProps }) => (
              <TableContainer title="Catalogue" description="All Firstout SKUs">
                <Table {...getTableProps()}>
                  <TableHead>
                    <TableRow>
                      {headers.map((header) => (
                        <TableHeader {...getHeaderProps({ header })} key={header.key}>
                          {header.key === "select" ? (
                            <Checkbox
                              id="catalogue-select-all"
                              labelText="Select all"
                              hideLabel
                              checked={allPageSelected}
                              indeterminate={
                                !allPageSelected && skus.some((sku) => selectedById.has(sku.id))
                              }
                              onChange={() => toggleSelectPage()}
                            />
                          ) : (
                            header.header
                          )}
                        </TableHeader>
                      ))}
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {tableRows.length === 0 ? (
                      <TableRow>
                        <TableCell colSpan={headers.length}>
                          No SKUs match the current filters.
                        </TableCell>
                      </TableRow>
                    ) : (
                      tableRows.map((row) => {
                        const entry = pagedSkus.find((sku) => sku.id === row.id);
                        return (
                          <TableRow
                            {...getRowProps({
                              row,
                              onClick: () => {
                                if (entry) {
                                  router.push(`/catalogue/${entry.id}`);
                                }
                              },
                            })}
                            key={row.id}
                            style={{ cursor: entry ? "pointer" : undefined }}
                          >
                            {row.cells.map((cell) => {
                              if (cell.info.header === "select" && entry) {
                                return (
                                  <TableCell
                                    key={cell.id}
                                    onClick={(event) => event.stopPropagation()}
                                  >
                                    <Checkbox
                                      id={`catalogue-select-${entry.id}`}
                                      labelText={`Select ${entry.our_ref}`}
                                      hideLabel
                                      checked={selectedById.has(entry.id)}
                                      onChange={() => toggleSelect(entry)}
                                    />
                                  </TableCell>
                                );
                              }
                              if (cell.info.header === "product" && entry) {
                                return (
                                  <TableCell key={cell.id}>
                                    <div
                                      style={{
                                        display: "flex",
                                        alignItems: "center",
                                        gap: "0.75rem",
                                      }}
                                    >
                                      {entry.photo_storage_key ? (
                                        <img
                                          src={skuPhotoUrl(entry.id)}
                                          alt={entry.name}
                                          width={48}
                                          height={48}
                                          style={{ objectFit: "cover", flexShrink: 0 }}
                                        />
                                      ) : null}
                                      <div>
                                        <div className="cds--type-semibold">{entry.our_ref}</div>
                                        <div className="cds--type-caption-01">{entry.name}</div>
                                        {entry.is_kit ? (
                                          <Tag type="teal" size="sm">
                                            Kit
                                          </Tag>
                                        ) : null}
                                      </div>
                                    </div>
                                  </TableCell>
                                );
                              }
                              if (cell.info.header === "lead_time_days" && entry) {
                                return (
                                  <TableCell key={cell.id}>
                                    <div>{formatLeadTime(entry.lead_time_days)}</div>
                                    <div className="cds--type-caption-01">
                                      {formatObservedMedianLine(leadBySku.get(entry.id))}
                                    </div>
                                  </TableCell>
                                );
                              }
                              if (
                                cell.info.header === "cost_zar" ||
                                cell.info.header === "stockist_inc_vat" ||
                                cell.info.header === "wholesale_inc_vat" ||
                                cell.info.header === "decorator_inc_vat" ||
                                cell.info.header === "retail_inc_vat"
                              ) {
                                return (
                                  <TableCell key={cell.id} style={{ textAlign: "right" }}>
                                    {cell.value}
                                  </TableCell>
                                );
                              }
                              if (cell.info.header === "actions" && entry) {
                                return (
                                  <TableCell
                                    key={cell.id}
                                    className="firstout-catalogue-actions-cell"
                                    onClick={(event) => event.stopPropagation()}
                                  >
                                    <div className="firstout-catalogue-row-actions">
                                      <Button
                                        type="button"
                                        kind="ghost"
                                        size="sm"
                                        hasIconOnly
                                        iconDescription="Print label"
                                        renderIcon={Barcode}
                                        onClick={(event) => {
                                          event.preventDefault();
                                          event.stopPropagation();
                                          printSkuLabels([entry]);
                                        }}
                                      />
                                      <FeatureFlags
                                        enableV12Overflowmenu
                                        enableV12DynamicFloatingStyles
                                      >
                                        <OverflowMenu
                                          size="sm"
                                          flipped
                                          menuOptionsClass="firstout-catalogue-overflow-menu"
                                          {...({
                                            autoAlign: true,
                                            menuAlignment: "bottom-end",
                                            label: `Actions for ${entry.our_ref}`,
                                          } as Record<string, unknown>)}
                                        >
                                          <MenuItem
                                            label="Print label"
                                            onClick={() => printSkuLabels([entry])}
                                          />
                                        </OverflowMenu>
                                      </FeatureFlags>
                                    </div>
                                  </TableCell>
                                );
                              }
                              return <TableCell key={cell.id}>{cell.value}</TableCell>;
                            })}
                          </TableRow>
                        );
                      })
                    )}
                  </TableBody>
                </Table>
              </TableContainer>
            )}
          </DataTable>
          <Pagination
            page={page}
            pageSize={pageSize}
            pageSizes={[10, 25, 50]}
            totalItems={total}
            onChange={({ page: nextPage, pageSize: nextSize }) => {
              setPage(nextPage);
              setPageSize(nextSize);
              setLoading(true);
            }}
          />
        </div>
      )}
    </Stack>
  );
}

export default function CataloguePage() {
  return (
    <Suspense fallback={<p className="cds--type-body-01">Loading catalogue…</p>}>
      <CataloguePageContent />
    </Suspense>
  );
}
