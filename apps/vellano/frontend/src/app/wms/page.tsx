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
import { useCallback, useEffect, useMemo, useState, useSyncExternalStore } from "react";

import { BinSelect, LocationBinFields } from "@/components/bin-select";
import { WmsLocationBar } from "@/components/wms-location-bar";
import { WmsScanField } from "@/components/wms-scan-field";
import { useLocationBins } from "@/hooks/use-location-bins";
import {
  ApiError,
  canReceive,
  canTransfer,
  completeStocktake,
  createTransfer,
  dispatchTransfer,
  downloadTransferPdf,
  getStocktake,
  isActiveLocation,
  listInventory,
  listLocations,
  listPurchaseOrders,
  listSkus,
  listStocktakes,
  listTransfers,
  lookupStocktakeBarcode,
  patchStocktakeLine,
  receivePurchaseOrder,
  receiveTransfer,
  startStocktake,
  type InventorySku,
  type Location,
  type PurchaseOrder,
  type Sku,
  type Stocktake,
  type StocktakeLine,
  type Transfer,
} from "@/lib/api";
import { optionalMovementBinId } from "@/lib/bin-helpers";
import { formatExpectedCartons } from "@/lib/carton-helpers";
import { useAuth } from "@/lib/auth";
import {
  getNarrowViewportServerSnapshot,
  getNarrowViewportSnapshot,
  subscribeNarrowViewport,
} from "@/lib/viewport";
import { useWmsFloorLocation } from "@/lib/wms-location";

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

function WmsDesktopInterstitial() {
  return (
    <div className="vellano-wms-interstitial">
      <Stack gap={6}>
        <div>
          <h1 className="cds--type-productive-heading-04">Warehouse</h1>
          <p className="cds--type-body-01">
            The warehouse console is built for your phone on the shop floor. Open this page on a
            mobile device to receive, count, and transfer stock with the camera scanner.
          </p>
        </div>
        <InlineNotification
          kind="info"
          title="Use this on your phone"
          subtitle="Receive, count, and transfer are easier with the floor scanner and bottom tabs on a narrow screen."
          hideCloseButton
          lowContrast
        />
        <Link href="/receive">Go to Receive (desktop)</Link>
      </Stack>
    </div>
  );
}

export default function WmsPage() {
  const narrow = useSyncExternalStore(
    subscribeNarrowViewport,
    getNarrowViewportSnapshot,
    getNarrowViewportServerSnapshot,
  );

  if (!narrow) {
    return <WmsDesktopInterstitial />;
  }

  return <WmsMobileConsole />;
}

function WmsMobileConsole() {
  const { user } = useAuth();
  const canRecv = canReceive(user);
  const canXfer = canTransfer(user);

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

  const { floor, locationId, setLocationId } = useWmsFloorLocation(locations);

  return (
    <div className="vellano-wms">
      {floor.length > 0 ? (
        <WmsLocationBar floor={floor} locationId={locationId} onChange={setLocationId} />
      ) : null}

      <div className="vellano-wms-content">
        <Stack gap={6}>
          <div>
            <h1 className="cds--type-productive-heading-04">Warehouse</h1>
            <p className="cds--type-body-01">
              Scan-first receive, stocktake count, and two-step transfers. Destination stock updates
              only after receive.
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
              locationId={locationId}
              landedOrders={landedOrders}
              locations={locations}
              skus={skus}
              onError={setError}
              onSuccess={setSuccess}
              onReceived={loadData}
            />
          ) : tab === "count" ? (
            <CountTab
              canMutate={canRecv}
              floorLocationId={locationId}
              stocktake={stocktake}
              onError={setError}
              onSuccess={setSuccess}
              onStocktakeChange={setStocktake}
              onReload={loadData}
            />
          ) : (
            <TransferTab
              canMutate={canXfer}
              floorLocationId={locationId}
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

      <div className="vellano-wms-switcher">
        <ContentSwitcher
          selectedIndex={TAB_INDEX[tab]}
          size="lg"
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
    </div>
  );
}

type ReceiveTabProps = {
  canMutate: boolean;
  locationId: string;
  locations: Location[];
  landedOrders: PurchaseOrder[];
  skus: Sku[];
  onError: (message: string) => void;
  onSuccess: (message: string) => void;
  onReceived: () => Promise<void>;
};

function ReceiveTab({
  canMutate,
  locationId,
  locations,
  landedOrders,
  skus,
  onError,
  onSuccess,
  onReceived,
}: ReceiveTabProps) {
  const [poId, setPoId] = useState("");
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

  const standingLocation = locations.find((entry) => entry.id === locationId);

  return (
    <Stack gap={5}>
      <WmsScanField
        id="wms-receive-barcode"
        labelText="Scan piece"
        placeholder="Scan or type our barcode"
        helperText="Scan the piece coming in, then choose the landed PO."
        value={barcode}
        disabled={!locationId}
        onChange={setBarcode}
      />
      {standingLocation ? (
        <p className="cds--type-label-01 vellano-muted-text">
          Receiving into <strong>{standingLocation.name}</strong> (change at top)
        </p>
      ) : null}
      <Select
        id="wms-receive-po"
        labelText="Landed purchase order"
        value={poId}
        onChange={(event) => {
          setPoId(event.target.value);
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
      {selectedPo ? (
        <p className="cds--type-body-01">{formatExpectedCartons(selectedPo, skus)}</p>
      ) : null}
      {landedOrders.length === 0 ? (
        <InlineNotification
          kind="info"
          title="No landed POs"
          subtitle="Land a purchase order before receiving."
          hideCloseButton
          lowContrast
        />
      ) : null}
      <LocationBinFields
        idPrefix="wms-receive"
        locationId={locationId}
        bins={activeBins}
        value={binId}
        onChange={setBinId}
        includeScan
      />
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
      <Button
        size="lg"
        disabled={submitting || !formValid}
        onClick={() => void handleReceive()}
      >
        {submitting ? "Receiving…" : "Receive"}
      </Button>
      <Link href="/receive">Full receive page</Link>
    </Stack>
  );
}

type CountTabProps = {
  canMutate: boolean;
  floorLocationId: string;
  stocktake: Stocktake | null;
  onError: (message: string) => void;
  onSuccess: (message: string) => void;
  onStocktakeChange: (stocktake: Stocktake | null) => void;
  onReload: () => Promise<void>;
};

function CountTab({
  canMutate,
  floorLocationId,
  stocktake,
  onError,
  onSuccess,
  onStocktakeChange,
  onReload,
}: CountTabProps) {
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
    if (!floorLocationId) {
      return;
    }
    setStarting(true);
    onError("");
    try {
      const created = await startStocktake({ location_id: floorLocationId });
      onStocktakeChange(created);
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

  async function handleLookup(code?: string) {
    if (!stocktake) {
      return;
    }
    const trimmed = (code ?? barcode).trim();
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
        <p className="cds--type-body-01">
          Start a stocktake at your standing location (switch at top), then scan each SKU to count.
        </p>
        <Button
          size="lg"
          disabled={starting || !floorLocationId}
          onClick={() => void handleStart()}
        >
          {starting ? "Starting…" : "Start stocktake"}
        </Button>
        <Link href="/stocktakes">Full stocktakes table</Link>
      </Stack>
    );
  }

  const locationMismatch =
    floorLocationId && stocktake.location_id !== floorLocationId;

  return (
    <Stack gap={5}>
      <div>
        <h2 className="cds--type-productive-heading-03">{stocktake.location_name}</h2>
        <p className="cds--type-body-01">In-progress stocktake — scan to count that SKU.</p>
      </div>
      {locationMismatch ? (
        <InlineNotification
          kind="warning"
          title="Different standing location"
          subtitle="Switch to the stocktake location at the top, or complete this count on the desktop Stocktakes page."
          hideCloseButton
          lowContrast
        />
      ) : null}
      <WmsScanField
        id="wms-count-barcode"
        labelText="Scan SKU"
        placeholder="Scan or type our barcode"
        value={barcode}
        onChange={setBarcode}
        onSubmit={(code) => void handleLookup(code)}
      />
      <Button
        size="lg"
        disabled={lookingUp || !barcode.trim()}
        onClick={() => void handleLookup()}
      >
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
          <Button size="lg" disabled={saving} onClick={() => void handleSaveCount()}>
            {saving ? "Saving…" : "Save count"}
          </Button>
        </div>
      ) : null}
      <Button size="lg" disabled={completing} onClick={() => void handleComplete()}>
        {completing ? "Completing…" : "Complete stocktake"}
      </Button>
      <Link href="/stocktakes">Full stocktakes table</Link>
    </Stack>
  );
}

type TransferTabProps = {
  canMutate: boolean;
  floorLocationId: string;
  locations: Location[];
  skus: Sku[];
  inventoryBySku: Map<string, InventorySku>;
  onError: (message: string) => void;
  onSuccess: (message: string) => void;
  onTransferred: () => Promise<void>;
};

function fullQtyReceivePayload(transfer: Transfer) {
  return {
    lines: transfer.lines.map((line) => ({
      line_id: line.id,
      qty_received: line.qty_dispatched,
    })),
  };
}

function TransferTab({
  canMutate,
  floorLocationId,
  locations,
  skus,
  inventoryBySku,
  onError,
  onSuccess,
  onTransferred,
}: TransferTabProps) {
  const [barcode, setBarcode] = useState("");
  const [skuId, setSkuId] = useState("");
  const [fromLocationId, setFromLocationId] = useState(floorLocationId);
  const [toLocationId, setToLocationId] = useState("");
  const [fromBinId, setFromBinId] = useState("");
  const [toBinId, setToBinId] = useState("");
  const [qty, setQty] = useState("1");
  const [submitting, setSubmitting] = useState<"draft" | "dispatch" | null>(null);
  const [lastDraft, setLastDraft] = useState<Transfer | null>(null);
  const [inboundDestId, setInboundDestId] = useState(floorLocationId);
  const [inbound, setInbound] = useState<Transfer[]>([]);
  const [inboundBusyId, setInboundBusyId] = useState<string | null>(null);
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

  const loadInbound = useCallback(async (destId: string) => {
    if (!destId) {
      setInbound([]);
      return;
    }
    setInbound(await listTransfers({ status: "in_transit", to_location_id: destId }));
  }, []);

  useEffect(() => {
    if (floorLocationId) {
      setFromLocationId(floorLocationId);
      setInboundDestId(floorLocationId);
    }
  }, [floorLocationId]);

  useEffect(() => {
    void loadInbound(inboundDestId).catch((err: unknown) => {
      onError(err instanceof Error ? err.message : "Failed to load inbound transfers.");
    });
  }, [inboundDestId, loadInbound, onError]);

  if (!canMutate) {
    return (
      <InlineNotification
        kind="warning"
        title="Read only"
        subtitle="WMS create and dispatch need owner or warehouse. Till users receive inbound transfers on the Transfers page."
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

  function draftPayload() {
    if (!formValid || numericQty === null) {
      return null;
    }
    return {
      from_location_id: fromLocationId,
      to_location_id: toLocationId,
      lines: [
        {
          sku_id: resolvedSkuId,
          qty: numericQty,
          from_bin_id: optionalMovementBinId(fromBinId, fromDefaultBinId),
          to_bin_id: optionalMovementBinId(toBinId, toDefaultBinId),
        },
      ],
    };
  }

  function resetLine() {
    setBarcode("");
    setSkuId("");
    setQty("1");
  }

  async function handleSaveDraft() {
    const payload = draftPayload();
    if (!payload) {
      return;
    }
    setSubmitting("draft");
    onError("");
    try {
      const created = await createTransfer(payload);
      setLastDraft(created);
      onSuccess(
        `${created.transfer_number} saved as draft. Destination stock is unchanged until receive.`,
      );
      resetLine();
      await onTransferred();
    } catch (err) {
      if (err instanceof ApiError && (err.status === 409 || err.status === 400)) {
        onError(err.message);
      } else {
        onError(err instanceof Error ? err.message : "Failed to save transfer draft.");
      }
    } finally {
      setSubmitting(null);
    }
  }

  async function handleDispatch() {
    setSubmitting("dispatch");
    onError("");
    try {
      let draft = lastDraft;
      if (!draft) {
        const payload = draftPayload();
        if (!payload) {
          setSubmitting(null);
          return;
        }
        draft = await createTransfer(payload);
      }
      const dispatched = await dispatchTransfer(draft.id);
      setLastDraft(null);
      onSuccess(
        `${dispatched.transfer_number} dispatched. Source stock decreased. Destination stock updates only after receive.`,
      );
      resetLine();
      await onTransferred();
      await loadInbound(inboundDestId);
    } catch (err) {
      if (err instanceof ApiError && (err.status === 409 || err.status === 400)) {
        onError(err.message);
      } else {
        onError(err instanceof Error ? err.message : "Failed to dispatch transfer.");
      }
    } finally {
      setSubmitting(null);
    }
  }

  async function handleInboundReceive(entry: Transfer) {
    setInboundBusyId(entry.id);
    onError("");
    try {
      const received = await receiveTransfer(entry.id, fullQtyReceivePayload(entry));
      onSuccess(`${received.transfer_number} received. Destination stock updated.`);
      await loadInbound(inboundDestId);
      await onTransferred();
    } catch (err) {
      if (err instanceof ApiError && (err.status === 409 || err.status === 400 || err.status === 403)) {
        onError(err.message);
      } else {
        onError(err instanceof Error ? err.message : "Failed to receive transfer.");
      }
    } finally {
      setInboundBusyId(null);
    }
  }

  async function handleInboundPrint(entry: Transfer) {
    setInboundBusyId(entry.id);
    onError("");
    try {
      await downloadTransferPdf(entry.id, entry.transfer_number);
      onSuccess(`Downloaded ${entry.transfer_number} transfer note.`);
    } catch (err) {
      onError(err instanceof Error ? err.message : "Failed to download transfer note.");
    } finally {
      setInboundBusyId(null);
    }
  }

  return (
    <Stack gap={5}>
      <WmsScanField
        id="wms-transfer-barcode"
        labelText="Scan piece"
        placeholder="Scan or type our barcode"
        helperText="Scan the piece being moved, then set quantity and destination."
        value={barcode}
        onChange={handleBarcodeChange}
      />
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
      {lastDraft ? (
        <InlineNotification
          kind="info"
          title={lastDraft.transfer_number}
          subtitle="Draft ready. Dispatch decreases source stock; destination still waits for receive."
          hideCloseButton
          lowContrast
        />
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
      <p className="cds--type-label-01 vellano-muted-text">
        Save draft does not move stock. Dispatch decreases source only — destination stock updates on
        receive.
      </p>
      <Button
        size="lg"
        disabled={submitting !== null || !formValid}
        onClick={() => void handleSaveDraft()}
      >
        {submitting === "draft" ? "Saving…" : "Save draft"}
      </Button>
      <Button
        kind="secondary"
        size="lg"
        disabled={submitting !== null || (!lastDraft && !formValid)}
        onClick={() => void handleDispatch()}
      >
        {submitting === "dispatch" ? "Dispatching…" : "Dispatch"}
      </Button>
      <h2 className="cds--type-productive-heading-03">Inbound receive</h2>
      <p className="cds--type-body-01">
        Receive in-transit transfers into a destination. This is the step that increases dest
        on-hand.
      </p>
      <Select
        id="wms-inbound-dest"
        labelText="Destination location"
        value={inboundDestId}
        onChange={(event) => setInboundDestId(event.target.value)}
      >
        <SelectItem value="" text="Select destination" />
        {locations.map((entry) => (
          <SelectItem key={entry.id} value={entry.id} text={entry.name} />
        ))}
      </Select>
      {inboundDestId && inbound.length === 0 ? (
        <p className="cds--type-body-01">No inbound transfers in transit to this location.</p>
      ) : null}
      {inbound.map((entry) => {
        const busy = inboundBusyId === entry.id;
        const summary = entry.lines
          .map((line) => `${line.qty_dispatched} × ${line.sku_our_ref}`)
          .join(", ");
        return (
          <div key={entry.id} className="vellano-wms-line-card">
            <p className="cds--type-body-01">
              <strong>{entry.transfer_number}</strong> — {entry.from_location_name} →{" "}
              {entry.to_location_name}
            </p>
            <p className="cds--type-label-01 vellano-muted-text">{summary || "No lines"}</p>
            <Button size="sm" disabled={busy} onClick={() => void handleInboundReceive(entry)}>
              {busy ? "Receiving…" : "Receive"}
            </Button>{" "}
            <Button
              kind="ghost"
              size="sm"
              disabled={busy}
              onClick={() => void handleInboundPrint(entry)}
            >
              Print PDF
            </Button>
          </div>
        );
      })}
      <Link href="/transfers">Full transfers page</Link>
    </Stack>
  );
}
