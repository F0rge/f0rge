"use client";

import {
  Button,
  Checkbox,
  DataTable,
  InlineNotification,
  Modal,
  Stack,
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
import { Barcode, DocumentExport, DocumentImport, Printer, TrashCan } from "@carbon/icons-react";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useMemo, useState } from "react";

import { SkuPriceEditor } from "@/components/sku-price-editor";
import {
  ApiError,
  canMutateCatalogue,
  canViewCostAudit,
  deleteSku,
  formatPriceAmount,
  formatZarAmount,
  listInventory,
  listSkus,
  skuPhotoUrl,
  updateSku,
  type Sku,
  type UpdateSkuPricePayload,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { downloadCsv } from "@/lib/csv";

const TABLE_HEADERS = [
  { key: "select", header: "" },
  { key: "product", header: "SKU / Product Name" },
  { key: "category", header: "Category" },
  { key: "preferred_supplier", header: "Preferred supplier" },
  { key: "lead_time_days", header: "Lead time" },
  { key: "reorder_min", header: "Reorder min" },
  { key: "cost_zar", header: "Cost (ZAR)" },
  { key: "retail_inc_vat", header: "Retail Price" },
  { key: "wholesale_inc_vat", header: "Trade Price" },
  { key: "our_barcode", header: "Our barcode" },
  { key: "actions", header: "Actions" },
] as const;

type SkuIdentityForm = {
  our_ref: string;
  our_barcode: string;
  name: string;
  design: string;
  fabric: string;
  category: string;
};

function emptyIdentityForm(): SkuIdentityForm {
  return {
    our_ref: "",
    our_barcode: "",
    name: "",
    design: "",
    fabric: "",
    category: "",
  };
}

function identityFormFromSku(sku: Sku): SkuIdentityForm {
  return {
    our_ref: sku.our_ref,
    our_barcode: sku.our_barcode,
    name: sku.name,
    design: sku.design,
    fabric: sku.fabric,
    category: sku.category ?? "",
  };
}

function isIdentityFormValid(form: SkuIdentityForm): boolean {
  return Boolean(
    form.our_ref.trim() &&
      form.our_barcode.trim() &&
      form.name.trim() &&
      form.design.trim() &&
      form.fabric.trim(),
  );
}

type SkuRow = {
  id: string;
  product: string;
  category: string;
  preferred_supplier: string;
  lead_time_days: string;
  reorder_min: string;
  cost_zar: string;
  retail_inc_vat: string;
  wholesale_inc_vat: string;
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

function escapeHtml(value: string): string {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function formatIncVatPrice(value: string | null | undefined): string {
  if (!value) {
    return "—";
  }
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) {
    return value;
  }
  return formatZarAmount(formatPriceAmount(parsed));
}

function printSkuLabels(targetSkus: Sku[]): void {
  if (targetSkus.length === 0) {
    return;
  }
  const printWindow = window.open("", "_blank", "noopener,noreferrer");
  if (!printWindow) {
    return;
  }
  const labelsHtml = targetSkus
    .map(
      (sku) => `
    <div class="label">
      <div class="name">${escapeHtml(sku.name)}</div>
      <div class="ref">${escapeHtml(sku.our_ref)}</div>
      <div class="barcode">${escapeHtml(sku.our_barcode)}</div>
    </div>`,
    )
    .join("");
  printWindow.document.write(`<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Barcode labels</title>
  <style>
    body { font-family: "IBM Plex Sans", sans-serif; margin: 1.5rem; color: #161616; }
    .label { page-break-inside: avoid; margin-bottom: 2rem; padding: 1rem; border: 1px solid #e0e0e0; }
    .name { font-size: 1rem; margin-bottom: 0.25rem; }
    .ref { font-weight: 600; margin-bottom: 0.5rem; }
    .barcode { font-family: monospace; font-size: 1.75rem; font-weight: 600; letter-spacing: 0.05em; }
    @media print { body { margin: 0; } .label { border: none; } }
  </style>
</head>
<body>${labelsHtml}</body>
</html>`);
  printWindow.document.close();
  printWindow.focus();
  printWindow.print();
}

function CataloguePageContent() {
  const { user } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();
  const canMutate = canMutateCatalogue(user?.role);
  const [skus, setSkus] = useState<Sku[]>([]);
  const [unitCostBySku, setUnitCostBySku] = useState<Map<string, string>>(new Map());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [priceSku, setPriceSku] = useState<Sku | null>(null);
  const [editSku, setEditSku] = useState<Sku | null>(null);
  const [editForm, setEditForm] = useState<SkuIdentityForm>(emptyIdentityForm);
  const [skuToDelete, setSkuToDelete] = useState<Sku | null>(null);
  const [saving, setSaving] = useState(false);
  const [identitySaving, setIdentitySaving] = useState(false);
  const [deleteSaving, setDeleteSaving] = useState(false);
  const [searchFilter, setSearchFilter] = useState("");
  const [categoryFilter, setCategoryFilter] = useState<string | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(() => new Set());
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);

  const loadSkus = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [skuData, inventoryData] = await Promise.all([listSkus(), listInventory()]);
      setSkus(skuData);
      const costs = new Map<string, string>();
      for (const entry of inventoryData) {
        if (entry.unit_cost_zar) {
          costs.set(entry.sku_id, entry.unit_cost_zar);
        }
      }
      setUnitCostBySku(costs);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load catalogue.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (user) {
      void loadSkus();
    }
  }, [user, loadSkus]);

  useEffect(() => {
    if (searchParams.get("new") !== "1") {
      return;
    }
    router.replace("/catalogue/new");
  }, [searchParams, router]);

  const categories = useMemo(() => {
    const values = new Set<string>();
    for (const sku of skus) {
      const category = sku.category?.trim();
      if (category) {
        values.add(category);
      }
    }
    return Array.from(values).sort((a, b) => a.localeCompare(b));
  }, [skus]);

  const filteredSkus = useMemo(() => {
    const query = searchFilter.trim().toLowerCase();
    return skus.filter((sku) => {
      if (categoryFilter && sku.category?.trim() !== categoryFilter) {
        return false;
      }
      if (!query) {
        return true;
      }
      return (
        sku.name.toLowerCase().includes(query) ||
        sku.our_ref.toLowerCase().includes(query) ||
        sku.our_barcode.toLowerCase().includes(query)
      );
    });
  }, [skus, categoryFilter, searchFilter]);

  useEffect(() => {
    setPage(1);
  }, [searchFilter, categoryFilter]);

  const pagedSkus = useMemo(() => {
    const start = (page - 1) * pageSize;
    return filteredSkus.slice(start, start + pageSize);
  }, [filteredSkus, page, pageSize]);

  const allFilteredSelected =
    filteredSkus.length > 0 && filteredSkus.every((sku) => selectedIds.has(sku.id));

  const rows: SkuRow[] = pagedSkus.map((entry) => ({
    id: entry.id,
    product: entry.id,
    category: entry.category?.trim() || "—",
    preferred_supplier: entry.preferred_supplier_name?.trim() || "—",
    lead_time_days: formatLeadTime(entry.lead_time_days),
    reorder_min: entry.reorder_min !== null ? String(entry.reorder_min) : "—",
    cost_zar: formatZarAmount(unitCostBySku.get(entry.id) ?? null),
    retail_inc_vat: formatIncVatPrice(entry.retail_inc_vat),
    wholesale_inc_vat: formatIncVatPrice(entry.wholesale_inc_vat),
    our_barcode: entry.our_barcode,
    select: entry.id,
    actions: entry.id,
  }));

  function openPriceEditor(entry: Sku) {
    setPriceSku(entry);
  }

  function openEditSku(entry: Sku) {
    setEditSku(entry);
    setEditForm(identityFormFromSku(entry));
  }

  async function handleEditSkuSave() {
    if (!editSku || !isIdentityFormValid(editForm)) {
      return;
    }
    setIdentitySaving(true);
    setError(null);
    try {
      const payload: UpdateSkuPricePayload = {
        our_ref: editForm.our_ref.trim(),
        our_barcode: editForm.our_barcode.trim(),
        name: editForm.name.trim(),
        design: editForm.design.trim(),
        fabric: editForm.fabric.trim(),
        category: editForm.category.trim() || null,
      };
      await updateSku(editSku.id, payload);
      setEditSku(null);
      setEditForm(emptyIdentityForm());
      await loadSkus();
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setError(err.message);
      } else {
        setError(err instanceof Error ? err.message : "Failed to update SKU.");
      }
    } finally {
      setIdentitySaving(false);
    }
  }

  async function handleDeleteSku() {
    if (!skuToDelete) {
      return;
    }
    setDeleteSaving(true);
    setError(null);
    try {
      await deleteSku(skuToDelete.id);
      setSkuToDelete(null);
      setSelectedIds((prev) => {
        const next = new Set(prev);
        next.delete(skuToDelete.id);
        return next;
      });
      if (priceSku?.id === skuToDelete.id) {
        setPriceSku(null);
      }
      if (editSku?.id === skuToDelete.id) {
        setEditSku(null);
        setEditForm(emptyIdentityForm());
      }
      await loadSkus();
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setError(err.message);
      } else {
        setError(err instanceof Error ? err.message : "Failed to delete SKU.");
      }
      setSkuToDelete(null);
    } finally {
      setDeleteSaving(false);
    }
  }

  function toggleSelect(id: string) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  }

  function toggleSelectAllFiltered() {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (allFilteredSelected) {
        for (const sku of filteredSkus) {
          next.delete(sku.id);
        }
      } else {
        for (const sku of filteredSkus) {
          next.add(sku.id);
        }
      }
      return next;
    });
  }

  function handlePrintLabels() {
    const targetSkus =
      selectedIds.size > 0
        ? filteredSkus.filter((sku) => selectedIds.has(sku.id))
        : filteredSkus;
    printSkuLabels(targetSkus);
  }

  return (
    <Stack gap={6}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <div>
          <h1 className="cds--type-productive-heading-04">Catalogue</h1>
          <p className="cds--type-body-01">
            Manage products, pricing tiers, and generate barcode labels.
          </p>
        </div>
        <div className="vellano-catalogue-actions">
          <Button
            kind="secondary"
            renderIcon={DocumentExport}
            disabled={filteredSkus.length === 0}
            onClick={() => {
              downloadCsv(
                "vellano-catalogue.csv",
                [
                  "Our ref",
                  "Name",
                  "Category",
                  "Preferred supplier",
                  "Lead time",
                  "Reorder min",
                  "Cost (ZAR)",
                  "Retail inc VAT",
                  "Trade inc VAT",
                  "Our barcode",
                ],
                filteredSkus.map((sku) => [
                  sku.our_ref,
                  sku.name,
                  sku.category?.trim() || "",
                  sku.preferred_supplier_name?.trim() || "",
                  formatLeadTime(sku.lead_time_days),
                  sku.reorder_min !== null ? String(sku.reorder_min) : "",
                  unitCostBySku.get(sku.id) ?? "",
                  sku.retail_inc_vat ?? "",
                  sku.wholesale_inc_vat ?? "",
                  sku.our_barcode,
                ]),
              );
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
              <Button onClick={() => router.push("/catalogue/new")}>New SKU</Button>
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

      <SkuPriceEditor
        sku={priceSku}
        open={priceSku !== null}
        readOnly={!canMutate}
        showCostAudit={canViewCostAudit(user?.role)}
        unitCostZar={priceSku ? (unitCostBySku.get(priceSku.id) ?? null) : null}
        saving={saving}
        onSavingChange={setSaving}
        onClose={() => setPriceSku(null)}
        onSaved={loadSkus}
        onError={setError}
      />

      <Modal
        open={editSku !== null}
        modalHeading="Edit SKU"
        primaryButtonText={identitySaving ? "Saving…" : "Save"}
        secondaryButtonText="Cancel"
        onRequestClose={() => {
          setEditSku(null);
          setEditForm(emptyIdentityForm());
        }}
        onRequestSubmit={() => void handleEditSkuSave()}
        primaryButtonDisabled={identitySaving || !isIdentityFormValid(editForm)}
        size="md"
      >
        <Stack gap={5}>
          <TextInput
            id="edit-sku-our-ref"
            labelText="Our ref *"
            value={editForm.our_ref}
            onChange={(event) =>
              setEditForm((form) => ({ ...form, our_ref: event.target.value }))
            }
          />
          <TextInput
            id="edit-sku-our-barcode"
            labelText="Our barcode *"
            value={editForm.our_barcode}
            onChange={(event) =>
              setEditForm((form) => ({ ...form, our_barcode: event.target.value }))
            }
          />
          <TextInput
            id="edit-sku-name"
            labelText="Name *"
            value={editForm.name}
            onChange={(event) => setEditForm((form) => ({ ...form, name: event.target.value }))}
          />
          <TextInput
            id="edit-sku-design"
            labelText="Design *"
            value={editForm.design}
            onChange={(event) =>
              setEditForm((form) => ({ ...form, design: event.target.value }))
            }
          />
          <TextInput
            id="edit-sku-fabric"
            labelText="Fabric *"
            value={editForm.fabric}
            onChange={(event) =>
              setEditForm((form) => ({ ...form, fabric: event.target.value }))
            }
          />
          <TextInput
            id="edit-sku-category"
            labelText="Category"
            value={editForm.category}
            onChange={(event) =>
              setEditForm((form) => ({ ...form, category: event.target.value }))
            }
          />
        </Stack>
      </Modal>

      <Modal
        open={skuToDelete !== null}
        modalHeading="Delete SKU"
        primaryButtonText={deleteSaving ? "Deleting…" : "Delete"}
        secondaryButtonText="Cancel"
        danger
        primaryButtonDisabled={deleteSaving}
        onRequestClose={() => setSkuToDelete(null)}
        onRequestSubmit={() => void handleDeleteSku()}
      >
        <p className="cds--type-body-01">
          Delete <strong>{skuToDelete?.our_ref}</strong> ({skuToDelete?.name})? This cannot be
          undone.
        </p>
      </Modal>

      {loading ? (
        <p className="cds--type-body-01">Loading catalogue…</p>
      ) : skus.length === 0 ? (
        <InlineNotification
          kind="info"
          title="No SKUs"
          subtitle="No catalogue items have been added yet."
          hideCloseButton
          lowContrast
        />
      ) : (
        <div className="vellano-catalogue-panel">
          <div className="vellano-catalogue-toolbar">
            <div className="vellano-catalogue-toolbar__left">
              <TextInput
                id="catalogue-search"
                labelText="Filter SKUs"
                hideLabel
                placeholder="Filter SKUs…"
                value={searchFilter}
                onChange={(event) => setSearchFilter(event.target.value)}
                size="md"
              />
              <div className="vellano-catalogue-toolbar__divider" aria-hidden />
              <div className="vellano-catalogue-chips" role="group" aria-label="Category filter">
                <Button
                  kind={categoryFilter === null ? "primary" : "ghost"}
                  size="sm"
                  onClick={() => setCategoryFilter(null)}
                >
                  All
                </Button>
                {categories.map((category) => (
                  <Button
                    key={category}
                    kind={categoryFilter === category ? "primary" : "ghost"}
                    size="sm"
                    onClick={() => setCategoryFilter(category)}
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

          <DataTable rows={rows} headers={[...TABLE_HEADERS]}>
            {({ rows: tableRows, headers, getTableProps, getHeaderProps, getRowProps }) => (
              <TableContainer title="Catalogue" description="All Vellano SKUs">
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
                              checked={allFilteredSelected}
                              indeterminate={!allFilteredSelected && filteredSkus.some((sku) => selectedIds.has(sku.id))}
                              onChange={() => toggleSelectAllFiltered()}
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
                                  openPriceEditor(entry);
                                }
                              },
                            })}
                            key={row.id}
                            style={{ cursor: entry ? "pointer" : undefined }}
                          >
                            {row.cells.map((cell) => {
                              if (cell.info.header === "select" && entry) {
                                return (
                                  <TableCell key={cell.id}>
                                    <Checkbox
                                      id={`catalogue-select-${entry.id}`}
                                      labelText={`Select ${entry.our_ref}`}
                                      hideLabel
                                      checked={selectedIds.has(entry.id)}
                                      onClick={(event) => event.stopPropagation()}
                                      onChange={() => toggleSelect(entry.id)}
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
                                      </div>
                                    </div>
                                  </TableCell>
                                );
                              }
                              if (
                                cell.info.header === "cost_zar" ||
                                cell.info.header === "retail_inc_vat" ||
                                cell.info.header === "wholesale_inc_vat"
                              ) {
                                return (
                                  <TableCell key={cell.id} style={{ textAlign: "right" }}>
                                    {cell.value}
                                  </TableCell>
                                );
                              }
                              if (cell.info.header === "actions" && entry) {
                                return (
                                  <TableCell key={cell.id} style={{ textAlign: "center" }}>
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
                                    {canMutate ? (
                                      <Button
                                        type="button"
                                        kind="ghost"
                                        size="sm"
                                        onClick={(event) => {
                                          event.preventDefault();
                                          event.stopPropagation();
                                          openEditSku(entry);
                                        }}
                                      >
                                        Edit SKU
                                      </Button>
                                    ) : null}
                                    <Button
                                      type="button"
                                      kind="ghost"
                                      size="sm"
                                      onClick={(event) => {
                                        event.preventDefault();
                                        event.stopPropagation();
                                        openPriceEditor(entry);
                                      }}
                                    >
                                      {canMutate ? "Edit prices" : "View prices"}
                                    </Button>
                                    {canMutate ? (
                                      <Button
                                        type="button"
                                        kind="danger--ghost"
                                        size="sm"
                                        hasIconOnly
                                        iconDescription="Delete SKU"
                                        renderIcon={TrashCan}
                                        onClick={(event) => {
                                          event.preventDefault();
                                          event.stopPropagation();
                                          setSkuToDelete(entry);
                                        }}
                                      />
                                    ) : null}
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
            totalItems={filteredSkus.length}
            onChange={({ page: nextPage, pageSize: nextSize }) => {
              setPage(nextPage);
              setPageSize(nextSize);
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
