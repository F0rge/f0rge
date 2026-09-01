"use client";

import {
  Button,
  ContentSwitcher,
  InlineNotification,
  Link,
  Select,
  SelectItem,
  Stack,
  Switch,
  TextInput,
} from "@carbon/react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { BinSelect, LocationBinFields } from "@/components/bin-select";
import { useLocationBins } from "@/hooks/use-location-bins";
import {
  ApiError,
  canReceive,
  canTransfer,
  completeStocktake,
  createTransfer,
  getStocktake,
  isActiveLocation,
  listInventory,
  listLocations,
  listPurchaseOrders,
  listSkus,
  listStocktakes,
  lookupStocktakeBarcode,
  patchStocktakeLine,
  receivePurchaseOrder,
  startStocktake,
  type InventorySku,
  type Location,
  type PurchaseOrder,
  type Sku,
  type Stocktake,
  type StocktakeLine,
} from "@/lib/api";
import { optionalMovementBinId } from "@/lib/bin-helpers";
import { useAuth } from "@/lib/auth";

type WmsTab = "receive" | "count" | "transfer";

const TAB_INDEX: Record<WmsTab, number> = {
  receive: 0,
  count: 1,
  transfer: 2,
};

const INDEX_TAB: WmsTab[] = ["receive", "count", "transfer"];

function findSkuByBarcode(skus: Sku[], barcode: string): Sku | undefined {
  const trimmed = barcode.trim();
  if (!trimmed) {
    return undefined;
  }
  return skus.find((sku) => sku.our_barcode === trimmed);
}

function parsePositiveInt(value: string): number | null {
  const trimmed = value.trim();
  if (!trimmed) {
    return null;
  }
  const parsed = Number(trimmed);
  if (!Number.isInteger(parsed) || parsed < 0) {
    return null;
  }
  return parsed;
}

export default function WmsPage() {
  const { user } = useAuth();
  const canRecv = canReceive(user?.role);
  const canXfer = canTransfer(user?.role);

  const [tab, setTab] = useState<WmsTab>("receive");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const [locations, setLocations] = useState<Location[]>([]);
  const [orders, setOrders] = useState<PurchaseOrder[]>([]);
  const [skus, setSkus] = useState<Sku[]>([]);
  const [inventory, setInventory] = useState<InventorySku[]>([]);
  const [stocktake, setStocktake] = useState<Stocktake | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [locationData, orderData, skuData, inventoryData, stocktakeSummaries] =
        await Promise.all([
          listLocations(),
          listPurchaseOrders(),
          listSkus(),
          listInventory(),
          listStocktakes(),
        ]);
      setLocations(locationData.filter(isActiveLocation));
      setOrders(orderData);
      setSkus(skuData);
      setInventory(inventoryData);
      const activeSummary = stocktakeSummaries.find(
        (entry) => entry.status === "in_progress",
      );
      if (activeSummary) {
        setStocktake(await getStocktake(activeSummary.id));
      } else {
        setStocktake(null);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load warehouse data.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (user) {
      void loadData();
    }
  }, [user, loadData]);

  const landedOrders = useMemo(
    () => orders.filter((entry) => entry.status === "landed"),
    [orders],
  );

  const inventoryBySku = useMemo(
    () => new Map(inventory.map((entry) => [entry.sku_id, entry])),
    [inventory],
  );

  function clearFeedback() {
    setError(null);
    setSuccess(null);
  }

  return (
    <div className="vellano-wms">
      <div className="vellano-wms-switcher">
        <ContentSwitcher
          selectedIndex={TAB_INDEX[tab]}
          onChange={(event) => {
            const index = event.index ?? 0;
            setTab(INDEX_TAB[index] ?? "receive");
            clearFeedback();
          }}
        >
          <Switch name="receive" text="Receive" />
          <Switch name="count" text="Count" />
          <Switch name="transfer" text="Transfer" />
        </ContentSwitcher>
      </div>

      <div className="vellano-wms-content">
        <Stack gap={6}>
          <div>
            <h1 className="cds--type-productive-heading-04">Warehouse (mobile)</h1>
            <p className="cds--type-body-01">
              Phone-friendly receive, stocktake count, and transfer flows.
            </p>
          </div>

          {success ? (
            <InlineNotification
              kind="success"
              title="Done"
              subtitle={success}
              onCloseButtonClick={() => setSuccess(null)}
              lowContrast
            />
          ) : null}

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
            <p className="cds--type-body-01">Loading…</p>
          ) : tab === "receive" ? (
            <ReceiveTab
              canMutate={canRecv}
              locations={locations}
              landedOrders={landedOrders}
              skus={skus}
              onError={setError}
              onSuccess={setSuccess}
              onReceived={loadData}
            />
          ) : tab === "count" ? (
            <CountTab
              canMutate={canRecv}
              locations={locations}
              stocktake={stocktake}
              onError={setError}
              onSuccess={setSuccess}
              onStocktakeChange={setStocktake}
              onReload={loadData}
            />
          ) : (
            <TransferTab
              canMutate={canXfer}
              locations={locations}
              skus={skus}
              inventoryBySku={inventoryBySku}
              onError={setError}
              onSuccess={setSuccess}
              onTransferred={loadData}
            />
          )}
        </Stack>
      </div>
    </div>
  );
}

type ReceiveTabProps = {
  canMutate: boolean;
  locations: Location[];
  landedOrders: PurchaseOrder[];
  skus: Sku[];
  onError: (message: string) => void;
  onSuccess: (message: string) => void;
  onReceived: () => Promise<void>;
};

function ReceiveTab({
  canMutate,
  locations,
  landedOrders,
  skus,
  onError,
  onSuccess,
  onReceived,
}: ReceiveTabProps) {
  const [poId, setPoId] = useState("");
  const [locationId, setLocationId] = useState("");
  const [binId, setBinId] = useState("");
  const [barcode, setBarcode] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const { activeBins, defaultBinId } = useLocationBins(locationId);

  useEffect(() => {
    setBinId(defaultBinId);
  }, [locationId, defaultBinId]);

  const selectedPo = landedOrders.find((entry) => entry.id === poId);
  const matchedSku = findSkuByBarcode(skus, barcode);
  const poLine =
    matchedSku && selectedPo
      ? selectedPo.lines.find((line) => line.sku_id === matchedSku.id)
      : undefined;

  const formValid = Boolean(poId && locationId);

  if (!canMutate) {
    return (
      <InlineNotification
        kind="warning"
        title="Read only"
        subtitle="Receive requires owner or warehouse role. Use the desktop Receive page (/receive) when you have access."
        hideCloseButton
        lowContrast
      />
    );
  }

  async function handleReceive() {
    if (!formValid) {
      return;
    }
    setSubmitting(true);
    onError("");
    try {
      await receivePurchaseOrder({
        purchase_order_id: poId,
        location_id: locationId,
        bin_id: optionalMovementBinId(binId, defaultBinId),
      });
      const po = landedOrders.find((entry) => entry.id === poId);
      const location = locations.find((entry) => entry.id === locationId);
      onSuccess(
        `Received ${po?.po_number ?? "PO"} into ${location?.name ?? "location"}.`,
      );
      setPoId("");
      setLocationId("");
      setBinId("");
      setBarcode("");
      await onReceived();
    } catch (err) {
      if (err instanceof ApiError && (err.status === 403 || err.status === 409)) {
        onError(err.message);
      } else {
        onError(err instanceof Error ? err.message : "Failed to receive purchase order.");
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Stack gap={5}>
      <Select
        id="wms-receive-po"
        labelText="Landed purchase order"
        value={poId}
        onChange={(event) => {
          setPoId(event.target.value);
          setBarcode("");
        }}
      >
        <SelectItem value="" text="Select a landed PO" />
        {landedOrders.map((entry) => (
          <SelectItem
            key={entry.id}
            value={entry.id}
            text={`${entry.po_number} — ${entry.supplier_name}`}
          />
        ))}
      </Select>
      {landedOrders.length === 0 ? (
        <InlineNotification
          kind="info"
          title="No landed POs"
          subtitle="Land a purchase order before receiving."
          hideCloseButton
          lowContrast
        />
      ) : null}
      <Select
        id="wms-receive-location"
        labelText="Location"
        value={locationId}
        onChange={(event) => setLocationId(event.target.value)}
      >
        <SelectItem value="" text="Select a location" />
        {locations.map((entry) => (
          <SelectItem key={entry.id} value={entry.id} text={entry.name} />
        ))}
      </Select>
      <LocationBinFields
        idPrefix="wms-receive"
        locationId={locationId}
        bins={activeBins}
        value={binId}
        onChange={setBinId}
        includeScan
      />
      <div className="vellano-wms-barcode">
        <TextInput
          id="wms-receive-barcode"
          labelText="Barcode (optional)"
          placeholder="Scan our barcode to confirm SKU on PO"
          value={barcode}
          onChange={(event) => setBarcode(event.target.value)}
        />
      </div>
      {barcode.trim() && matchedSku && poLine ? (
        <div className="vellano-wms-line-card">
          <p className="cds--type-body-01">
            <strong>{matchedSku.our_ref}</strong> — {matchedSku.name}
          </p>
          <p className="cds--type-label-01 vellano-muted-text">
            On PO: qty {poLine.qty}
          </p>
        </div>
      ) : null}
      {barcode.trim() && matchedSku && selectedPo && !poLine ? (
        <InlineNotification
          kind="warning"
          title="Not on PO"
          subtitle={`${matchedSku.our_ref} is not on the selected purchase order.`}
          hideCloseButton
          lowContrast
        />
      ) : null}
      {barcode.trim() && !matchedSku ? (
        <InlineNotification
          kind="warning"
          title="Unknown barcode"
          subtitle="No catalogue SKU matches that our barcode."
          hideCloseButton
          lowContrast
        />
      ) : null}
      <Button disabled={submitting || !formValid} onClick={() => void handleReceive()}>
        {submitting ? "Receiving…" : "Receive"}
      </Button>
      <Link href="/receive">Full receive page</Link>
    </Stack>
  );
}

type CountTabProps = {
  canMutate: boolean;
  locations: Location[];
  stocktake: Stocktake | null;
  onError: (message: string) => void;
  onSuccess: (message: string) => void;
  onStocktakeChange: (stocktake: Stocktake | null) => void;
  onReload: () => Promise<void>;
};

function CountTab({
  canMutate,
  locations,
  stocktake,
  onError,
  onSuccess,
  onStocktakeChange,
  onReload,
}: CountTabProps) {
  const [locationId, setLocationId] = useState("");
  const [starting, setStarting] = useState(false);
  const [barcode, setBarcode] = useState("");
  const [activeLine, setActiveLine] = useState<StocktakeLine | null>(null);
  const [countQty, setCountQty] = useState("1");
  const [lookingUp, setLookingUp] = useState(false);
  const [saving, setSaving] = useState(false);
  const [completing, setCompleting] = useState(false);

  if (!canMutate) {
    return (
      <InlineNotification
        kind="warning"
        title="Read only"
        subtitle="Stocktake counting requires owner or warehouse role. Use the desktop Stocktakes page (/stocktakes) when you have access."
        hideCloseButton
        lowContrast
      />
    );
  }

  async function handleStart() {
    if (!locationId) {
      return;
    }
    setStarting(true);
    onError("");
    try {
      const created = await startStocktake({ location_id: locationId });
      onStocktakeChange(created);
      setLocationId("");
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        onError(err.message);
        await onReload();
      } else {
        onError(err instanceof Error ? err.message : "Failed to start stocktake.");
      }
    } finally {
      setStarting(false);
    }
  }

  async function handleLookup() {
    if (!stocktake) {
      return;
    }
    const trimmed = barcode.trim();
    if (!trimmed) {
      return;
    }
    setLookingUp(true);
    onError("");
    try {
      const line = await lookupStocktakeBarcode(stocktake.id, { barcode: trimmed });
      setBarcode("");
      setActiveLine(line);
      const nextQty =
        line.counted_qty !== null && line.counted_qty !== undefined
          ? line.counted_qty + 1
          : 1;
      setCountQty(String(nextQty));
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) {
        onError(err.message || "No line matches that barcode.");
      } else {
        onError(err instanceof Error ? err.message : "Barcode lookup failed.");
      }
    } finally {
      setLookingUp(false);
    }
  }

  async function handleSaveCount() {
    if (!stocktake || !activeLine) {
      return;
    }
    const qty = parsePositiveInt(countQty);
    if (qty === null) {
      onError("Enter a valid counted quantity (0 or more).");
      return;
    }
    setSaving(true);
    onError("");
    try {
      const updated = await patchStocktakeLine(stocktake.id, activeLine.id, {
        counted_qty: qty,
      });
      setActiveLine(updated);
      onStocktakeChange({
        ...stocktake,
        lines: stocktake.lines.map((entry) =>
          entry.id === updated.id ? updated : entry,
        ),
      });
      onSuccess(`Counted ${updated.our_ref}: ${qty}`);
    } catch (err) {
      onError(err instanceof Error ? err.message : "Failed to save count.");
    } finally {
      setSaving(false);
    }
  }

  async function handleComplete() {
    if (!stocktake) {
      return;
    }
    setCompleting(true);
    onError("");
    try {
      await completeStocktake(stocktake.id);
      onStocktakeChange(null);
      setActiveLine(null);
      onSuccess(`Stocktake at ${stocktake.location_name} completed.`);
      await onReload();
    } catch (err) {
      onError(err instanceof Error ? err.message : "Failed to complete stocktake.");
    } finally {
      setCompleting(false);
    }
  }

  if (!stocktake) {
    return (
      <Stack gap={5}>
        <Select
          id="wms-count-location"
          labelText="Location"
          value={locationId}
          onChange={(event) => setLocationId(event.target.value)}
        >
          <SelectItem value="" text="Select a location" />
          {locations.map((entry) => (
            <SelectItem key={entry.id} value={entry.id} text={entry.name} />
          ))}
        </Select>
        <Button disabled={starting || !locationId} onClick={() => void handleStart()}>
          {starting ? "Starting…" : "Start stocktake"}
        </Button>
        <Link href="/stocktakes">Full stocktakes table</Link>
      </Stack>
    );
  }

  return (
    <Stack gap={5}>
      <div>
        <h2 className="cds--type-productive-heading-03">{stocktake.location_name}</h2>
        <p className="cds--type-body-01">In-progress stocktake — scan to count.</p>
      </div>
      <div className="vellano-wms-barcode">
        <TextInput
          id="wms-count-barcode"
          labelText="Barcode"
          placeholder="Scan or type our barcode"
          value={barcode}
          onChange={(event) => setBarcode(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              event.preventDefault();
              void handleLookup();
            }
          }}
        />
      </div>
      <Button disabled={lookingUp || !barcode.trim()} onClick={() => void handleLookup()}>
        {lookingUp ? "Looking up…" : "Lookup"}
      </Button>
      {activeLine ? (
        <div className="vellano-wms-line-card">
          <p className="cds--type-body-01">
            <strong>{activeLine.our_ref}</strong> — {activeLine.name}
          </p>
          <p className="cds--type-label-01 vellano-muted-text">
            Expected {activeLine.expected_qty}
            {activeLine.counted_qty !== null ? ` • Counted ${activeLine.counted_qty}` : ""}
          </p>
          <TextInput
            id="wms-count-qty"
            labelText="Counted qty"
            value={countQty}
            onChange={(event) => setCountQty(event.target.value)}
            inputMode="numeric"
          />
          <Button disabled={saving} onClick={() => void handleSaveCount()}>
            {saving ? "Saving…" : "Save count"}
          </Button>
        </div>
      ) : null}
      <Button disabled={completing} onClick={() => void handleComplete()}>
        {completing ? "Completing…" : "Complete stocktake"}
      </Button>
      <Link href="/stocktakes">Full stocktakes table</Link>
    </Stack>
  );
}

type TransferTabProps = {
  canMutate: boolean;
  locations: Location[];
  skus: Sku[];
  inventoryBySku: Map<string, InventorySku>;
  onError: (message: string) => void;
  onSuccess: (message: string) => void;
  onTransferred: () => Promise<void>;
};

function TransferTab({
  canMutate,
  locations,
  skus,
  inventoryBySku,
  onError,
  onSuccess,
  onTransferred,
}: TransferTabProps) {
  const [barcode, setBarcode] = useState("");
  const [skuId, setSkuId] = useState("");
  const [fromLocationId, setFromLocationId] = useState("");
  const [toLocationId, setToLocationId] = useState("");
  const [fromBinId, setFromBinId] = useState("");
  const [toBinId, setToBinId] = useState("");
  const [qty, setQty] = useState("1");
  const [submitting, setSubmitting] = useState(false);
  const { activeBins: fromBins, defaultBinId: fromDefaultBinId } =
    useLocationBins(fromLocationId);
  const { activeBins: toBins, defaultBinId: toDefaultBinId } = useLocationBins(toLocationId);

  const matchedSku = findSkuByBarcode(skus, barcode);
  const resolvedSkuId = skuId || matchedSku?.id || "";
  const selectedSku = skus.find((entry) => entry.id === resolvedSkuId);
  const skuInventory = resolvedSkuId ? inventoryBySku.get(resolvedSkuId) : undefined;
  const sourceOnHand =
    skuInventory?.locations.find((loc) => loc.location_id === fromLocationId)?.on_hand ?? 0;

  const destinationOptions = locations.filter((loc) => loc.id !== fromLocationId);
  const sourceOptions = locations.filter((loc) => loc.id !== toLocationId);

  const numericQty = parsePositiveInt(qty);
  const formValid =
    Boolean(fromLocationId && toLocationId && resolvedSkuId) &&
    numericQty !== null &&
    numericQty > 0 &&
    numericQty <= sourceOnHand;

  if (!canMutate) {
    return (
      <InlineNotification
        kind="warning"
        title="Read only"
        subtitle="Transfers require owner or warehouse role. Use the desktop Transfers page (/transfers) when you have access."
        hideCloseButton
        lowContrast
      />
    );
  }

  function handleBarcodeChange(value: string) {
    setBarcode(value);
    const sku = findSkuByBarcode(skus, value);
    if (sku) {
      setSkuId(sku.id);
    }
  }

  async function handleTransfer() {
    if (!formValid || numericQty === null) {
      return;
    }
    setSubmitting(true);
    onError("");
    try {
      const result = await createTransfer({
        from_location_id: fromLocationId,
        to_location_id: toLocationId,
        sku_id: resolvedSkuId,
        qty: numericQty,
        from_bin_id: optionalMovementBinId(fromBinId, fromDefaultBinId),
        to_bin_id: optionalMovementBinId(toBinId, toDefaultBinId),
      });
      onSuccess(
        `Transferred ${result.qty} × ${result.our_ref} to ${result.to_location.location_name}.`,
      );
      setBarcode("");
      setSkuId("");
      setQty("1");
      await onTransferred();
    } catch (err) {
      if (err instanceof ApiError && (err.status === 409 || err.status === 400)) {
        onError(err.message);
      } else {
        onError(err instanceof Error ? err.message : "Failed to transfer stock.");
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Stack gap={5}>
      <div className="vellano-wms-barcode">
        <TextInput
          id="wms-transfer-barcode"
          labelText="Barcode"
          placeholder="Scan our barcode"
          value={barcode}
          onChange={(event) => handleBarcodeChange(event.target.value)}
        />
      </div>
      {barcode.trim() && !matchedSku ? (
        <InlineNotification
          kind="warning"
          title="Unknown barcode"
          subtitle="No catalogue SKU matches that our barcode."
          hideCloseButton
          lowContrast
        />
      ) : null}
      {selectedSku ? (
        <div className="vellano-wms-line-card">
          <p className="cds--type-body-01">
            <strong>{selectedSku.our_ref}</strong> — {selectedSku.name}
          </p>
        </div>
      ) : null}
      <Select
        id="wms-transfer-from"
        labelText="From location"
        value={fromLocationId}
        onChange={(event) => {
          setFromLocationId(event.target.value);
          setFromBinId("");
        }}
      >
        <SelectItem value="" text="Select source location" />
        {sourceOptions.map((entry) => (
          <SelectItem key={entry.id} value={entry.id} text={entry.name} />
        ))}
      </Select>
      {fromLocationId ? (
        <BinSelect
          id="wms-transfer-from-bin"
          labelText="From bin (optional)"
          value={fromBinId}
          bins={fromBins}
          onChange={setFromBinId}
          helperText="Leave as default to use the location default bin."
        />
      ) : null}
      <Select
        id="wms-transfer-to"
        labelText="To location"
        value={toLocationId}
        onChange={(event) => {
          setToLocationId(event.target.value);
          setToBinId("");
        }}
      >
        <SelectItem value="" text="Select destination location" />
        {destinationOptions.map((entry) => (
          <SelectItem key={entry.id} value={entry.id} text={entry.name} />
        ))}
      </Select>
      {toLocationId ? (
        <BinSelect
          id="wms-transfer-to-bin"
          labelText="To bin (optional)"
          value={toBinId}
          bins={toBins}
          onChange={setToBinId}
          helperText="Leave as default to use the location default bin."
        />
      ) : null}
      {fromLocationId && resolvedSkuId ? (
        <p className="cds--type-body-01">
          On hand at source: <strong>{sourceOnHand}</strong>
        </p>
      ) : null}
      <TextInput
        id="wms-transfer-qty"
        labelText="Quantity"
        value={qty}
        onChange={(event) => setQty(event.target.value)}
        inputMode="numeric"
        invalid={numericQty !== null && sourceOnHand > 0 && numericQty > sourceOnHand}
        invalidText={`Only ${sourceOnHand} available at source`}
        disabled={!resolvedSkuId}
      />
      <Button disabled={submitting || !formValid} onClick={() => void handleTransfer()}>
        {submitting ? "Transferring…" : "Transfer"}
      </Button>
      <Link href="/transfers">Full transfers page</Link>
    </Stack>
  );
}
