"use client";

import {
  Button,
  ComboBox,
  DataTable,
  InlineNotification,
  Modal,
  NumberInput,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableHeader,
  TableRow,
  Tag,
} from "@carbon/react";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  ApiError,
  canMutatePicks,
  createPick,
  listPicks,
  listSkus,
  previewPick,
  type PickDocument,
  type PickPreview,
  type Sku,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { PICK_STATUS_LABELS, pickStatusTagType } from "@/lib/picks";

const TABLE_HEADERS = [
  { key: "pick_number", header: "Pick" },
  { key: "sku", header: "Kit" },
  { key: "qty", header: "Qty" },
  { key: "status", header: "Status" },
  { key: "created_at", header: "Created" },
] as const;

function skuItemToString(item: Sku | null): string {
  return item ? `${item.our_ref} — ${item.name}` : "";
}

function shouldFilterSku({
  item,
  itemToString,
  inputValue,
}: {
  item: Sku;
  itemToString?: (item: Sku | null) => string;
  inputValue: string | null;
}): boolean {
  if (!inputValue) {
    return true;
  }
  const haystack = (itemToString ?? skuItemToString)(item).toLowerCase();
  return haystack.includes(inputValue.toLowerCase());
}

function formatDateTime(iso: string): string {
  if (!iso) {
    return "—";
  }
  return new Date(iso).toLocaleString("en-ZA");
}

function PicksPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { user } = useAuth();
  const canMutate = canMutatePicks(user);
  const [picks, setPicks] = useState<PickDocument[]>([]);
  const [skus, setSkus] = useState<Sku[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [skuId, setSkuId] = useState("");
  const [qty, setQty] = useState<number | "">(1);
  const [preview, setPreview] = useState<PickPreview | null>(null);
  const prefillConsumed = useRef(false);

  const kits = useMemo(() => skus.filter((sku) => sku.is_kit), [skus]);
  const selectedSku = kits.find((sku) => sku.id === skuId) ?? null;
  const numericQty = typeof qty === "number" ? qty : 0;

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [pickData, skuData] = await Promise.all([listPicks(), listSkus()]);
      setPicks(pickData);
      setSkus(skuData);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load picks.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (user) {
      void loadData();
    }
  }, [user, loadData]);

  useEffect(() => {
    if (!canMutate || prefillConsumed.current) {
      return;
    }
    const skuPrefill = searchParams.get("sku");
    const qtyPrefill = Number(searchParams.get("qty") ?? "");
    if (!skuPrefill) {
      return;
    }
    prefillConsumed.current = true;
    setSkuId(skuPrefill);
    setQty(Number.isFinite(qtyPrefill) && qtyPrefill > 0 ? qtyPrefill : 1);
    setCreateOpen(true);
    const next = new URLSearchParams(searchParams.toString());
    next.delete("sku");
    next.delete("qty");
    const qs = next.toString();
    router.replace(qs ? `/picks?${qs}` : "/picks");
  }, [canMutate, searchParams, router]);

  useEffect(() => {
    if (!createOpen || !skuId || numericQty < 1) {
      setPreview(null);
      return;
    }
    let cancelled = false;
    previewPick({ sku_id: skuId, qty: numericQty })
      .then((data) => {
        if (!cancelled) {
          setPreview(data);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setPreview(null);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [createOpen, skuId, numericQty]);

  const pickById = useMemo(
    () => Object.fromEntries(picks.map((entry) => [entry.id, entry])),
    [picks],
  );

  const rows = picks
    .slice()
    .sort((a, b) => b.created_at.localeCompare(a.created_at))
    .map((entry) => ({
      id: entry.id,
      pick_number: entry.pick_number || entry.id,
      sku: entry.sku_our_ref || entry.sku_id,
      qty: String(entry.qty),
      status: entry.status,
      created_at: formatDateTime(entry.created_at),
    }));

  async function handleCreate() {
    if (!canMutate || !skuId || numericQty < 1) {
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const created = await createPick({ sku_id: skuId, qty: numericQty });
      setCreateOpen(false);
      setSkuId("");
      setQty(1);
      router.push(`/picks/${created.id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to create pick.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Stack gap={6}>
      <div className="vellano-page-header">
        <div>
          <h1 className="cds--type-productive-heading-04">Picks</h1>
          <p className="cds--type-body-01">
            Allocate kit components across locations. Leave-behind is allowed.
          </p>
        </div>
        {canMutate ? <Button onClick={() => setCreateOpen(true)}>New pick</Button> : null}
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

      {loading ? (
        <p className="cds--type-body-01">Loading picks…</p>
      ) : picks.length === 0 ? (
        <InlineNotification
          kind="info"
          title="No picks"
          subtitle="No kit picks have been created yet."
          hideCloseButton
          lowContrast
        />
      ) : (
        <DataTable rows={rows} headers={[...TABLE_HEADERS]}>
          {({ rows: tableRows, headers, getTableProps, getHeaderProps, getRowProps }) => (
            <TableContainer title="Picks" description="Kit component allocations">
              <Table {...getTableProps()}>
                <TableHead>
                  <TableRow>
                    {headers.map((header) => (
                      <TableHeader {...getHeaderProps({ header })} key={header.key}>
                        {header.header}
                      </TableHeader>
                    ))}
                  </TableRow>
                </TableHead>
                <TableBody>
                  {tableRows.map((row) => {
                    const entry = pickById[row.id];
                    return (
                      <TableRow
                        {...getRowProps({ row })}
                        key={row.id}
                        onClick={() => router.push(`/picks/${row.id}`)}
                      >
                        {row.cells.map((cell) => (
                          <TableCell key={cell.id}>
                            {cell.info.header === "status" && entry ? (
                              <Tag type={pickStatusTagType(entry.status)} size="sm">
                                {PICK_STATUS_LABELS[entry.status]}
                              </Tag>
                            ) : cell.info.header === "sku" && entry ? (
                              <>
                                {entry.sku_our_ref || entry.sku_id}
                                {entry.sku_name ? (
                                  <div className="vellano-muted-text">{entry.sku_name}</div>
                                ) : null}
                              </>
                            ) : (
                              cell.value
                            )}
                          </TableCell>
                        ))}
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </TableContainer>
          )}
        </DataTable>
      )}

      <Modal
        open={createOpen}
        modalHeading="New pick"
        primaryButtonText={saving ? "Creating…" : "Create pick"}
        secondaryButtonText="Cancel"
        primaryButtonDisabled={!canMutate || !skuId || numericQty < 1 || saving}
        onRequestClose={() => setCreateOpen(false)}
        onRequestSubmit={() => void handleCreate()}
      >
        <Stack gap={5}>
          <ComboBox
            id="pick-kit"
            titleText="Kit SKU"
            placeholder="Search kit…"
            items={kits}
            itemToString={skuItemToString}
            selectedItem={selectedSku}
            shouldFilterItem={shouldFilterSku}
            onChange={({ selectedItem }) => setSkuId(selectedItem?.id ?? "")}
          />
          <NumberInput
            id="pick-qty"
            label="Quantity"
            min={1}
            step={1}
            value={qty}
            onChange={(_, { value }) => {
              setQty(value === "" ? "" : typeof value === "number" ? value : Number(value));
            }}
          />
          {preview?.needs_confirm ? (
            <InlineNotification
              kind="warning"
              title="Split pick"
              subtitle="This allocation splits a kit across locations and will need confirmation."
              hideCloseButton
              lowContrast
            />
          ) : null}
          {preview?.qty_short ? (
            <InlineNotification
              kind="error"
              title="Short pick"
              subtitle="Not enough component stock to fill this kit quantity."
              hideCloseButton
              lowContrast
            />
          ) : null}
        </Stack>
      </Modal>
    </Stack>
  );
}

export default function PicksPage() {
  return (
    <Suspense fallback={<p className="cds--type-body-01">Loading picks…</p>}>
      <PicksPageContent />
    </Suspense>
  );
}
