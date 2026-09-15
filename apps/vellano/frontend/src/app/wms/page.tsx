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
  canMutateDeliveries,
  canMutatePicks,
  completeStocktake,
  completeDelivery,
  completePick,
  confirmPick,
  createTransfer,
  dispatchTransfer,
  downloadTransferPdf,
  getDelivery,
  getSettings,
  getStocktake,
  getPurchaseOrder,
  isActiveLocation,
  listInventory,
  listLocations,
  listPurchaseOrders,
  listSkus,
  listStocktakes,
  listTransfers,
  loadDelivery,
  lookupStocktakeBarcode,
  listDeliveries,
  listPicks,
  packDelivery,
  patchStocktakeLine,
  receivePurchaseOrder,
  receiveTransfer,
  startStocktake,
  type Delivery,
  type InventorySku,
  type Location,
  type PurchaseOrder,
  type PurchaseOrderListItem,
  type Sku,
  type Stocktake,
  type StocktakeLine,
  type Transfer,
  updateDeliveryTracking,
} from "@/lib/api";
import type { PickDocument } from "@/lib/picks";
import { optionalMovementBinId } from "@/lib/bin-helpers";
import { formatExpectedCartons } from "@/lib/carton-helpers";
import { useAuth } from "@/lib/auth";
import {
  getWmsMobileViewportServerSnapshot,
  getWmsMobileViewportSnapshot,
  subscribeWmsMobileViewport,
} from "@/lib/viewport";
import { useWmsFloorLocation } from "@/lib/wms-location";

type WmsTab = "receive" | "count" | "transfer" | "pick" | "pack" | "deliver";

const TAB_INDEX: Record<WmsTab, number> = {
  receive: 0,
  count: 1,
  transfer: 2,
  pick: 3,
  pack: 4,
  deliver: 5,
};

const INDEX_TAB: WmsTab[] = ["receive", "count", "transfer", "pick", "pack", "deliver"];

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
            mobile device to receive, count, transfer, pick, pack, and deliver with the camera
            scanner.
          </p>
        </div>
        <InlineNotification
          kind="info"
          title="Use this on your phone"
          subtitle="Floor work is easier with the scanner and bottom tabs on a narrow screen."
          hideCloseButton
          lowContrast
        />
        <Link href="/receive">Go to Receive (desktop)</Link>
      </Stack>
    </div>
  );
}

export default function WmsPage() {
  const mobile = useSyncExternalStore(
    subscribeWmsMobileViewport,
    getWmsMobileViewportSnapshot,
    getWmsMobileViewportServerSnapshot,
  );

  if (!mobile) {
    return <WmsDesktopInterstitial />;
  }

  return <WmsMobileConsole />;
}

function WmsMobileConsole() {
  const { user } = useAuth();
  const canRecv = canReceive(user);
  const canXfer = canTransfer(user);
  const canPick = canMutatePicks(user);
  const canDlv = canMutateDeliveries(user);

  const [tab, setTab] = useState<WmsTab>("receive");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const [locations, setLocations] = useState<Location[]>([]);
  const [orders, setOrders] = useState<PurchaseOrderListItem[]>([]);
  const [skus, setSkus] = useState<Sku[]>([]);
  const [inventory, setInventory] = useState<InventorySku[]>([]);
  const [stocktake, setStocktake] = useState<Stocktake | null>(null);
  const [teamReceiveDefaultId, setTeamReceiveDefaultId] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [locationData, orderData, skuData, inventoryData, stocktakeSummaries, settingsData] =
        await Promise.all([
          listLocations(),
          listPurchaseOrders({ limit: 100 }),
          listSkus(),
          listInventory(),
          listStocktakes(),
          getSettings(),
        ]);
      setLocations(locationData.filter(isActiveLocation));
      setTeamReceiveDefaultId(settingsData.default_receive_location_id);
      setOrders(orderData.items);
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

  const { floor, locationId, setLocationId } = useWmsFloorLocation(
    locations,
    teamReceiveDefaultId,
  );

  return (
    <div className="vellano-wms">
      {floor ? (
        <WmsLocationBar floor={floor} locationId={locationId} onChange={setLocationId} />
      ) : null}

      <div className="vellano-wms-content">
        <Stack gap={6}>
          <div>
            <h1 className="cds--type-productive-heading-04">Warehouse</h1>
            <p className="cds--type-body-01">
              Scan-first receive, count, transfer, pick, pack, and deliver. Destination stock
              updates only after receive.
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
          ) : tab === "transfer" ? (
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
          ) : tab === "pick" ? (
            <PickTab canMutate={canPick} skus={skus} onError={setError} onSuccess={setSuccess} />
          ) : tab === "pack" ? (
            <PackTab canMutate={canDlv} skus={skus} onError={setError} onSuccess={setSuccess} />
          ) : (
            <DeliverTab canMutate={canDlv} onError={setError} onSuccess={setSuccess} />
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
          <Switch name="pick" text="Pick" />
          <Switch name="pack" text="Pack" />
          <Switch name="deliver" text="Deliver" />
        </ContentSwitcher>
      </div>
    </div>
  );
}

type ReceiveTabProps = {
  canMutate: boolean;
  locationId: string;
  locations: Location[];
  landedOrders: PurchaseOrderListItem[];
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
  const [selectedPoDetail, setSelectedPoDetail] = useState<PurchaseOrder | null>(null);
  const { activeBins, defaultBinId } = useLocationBins(locationId);

  useEffect(() => {
    setBinId(defaultBinId);
  }, [locationId, defaultBinId]);

  useEffect(() => {
    if (!poId) {
      setSelectedPoDetail(null);
      return;
    }
    let cancelled = false;
    void getPurchaseOrder(poId)
      .then((po) => {
        if (!cancelled) {
          setSelectedPoDetail(po);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setSelectedPoDetail(null);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [poId]);

  const selectedPoSummary = landedOrders.find((entry) => entry.id === poId);
  const matchedSku = findSkuByBarcode(skus, barcode);
  const poLine =
    matchedSku && selectedPoDetail
      ? selectedPoDetail.lines.find((line) => line.sku_id === matchedSku.id)
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
      {selectedPoDetail ? (
        <p className="cds--type-body-01">{formatExpectedCartons(selectedPoDetail, skus)}</p>
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
      {barcode.trim() && matchedSku && selectedPoSummary && !poLine ? (
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

  async function handleLookup(scannedCode?: string) {
    if (!stocktake) {
      return;
    }
    const trimmed = (scannedCode ?? barcode).trim();
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

type FulfillmentTabProps = {
  canMutate: boolean;
  onError: (message: string) => void;
  onSuccess: (message: string) => void;
};

function PickTab({
  canMutate,
  skus,
  onError,
  onSuccess,
}: FulfillmentTabProps & { skus: Sku[] }) {
  const [picks, setPicks] = useState<PickDocument[]>([]);
  const [barcode, setBarcode] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const reload = useCallback(async () => {
    setPicks(await listPicks("sales_order"));
  }, []);

  useEffect(() => {
    void reload().catch((err) =>
      onError(err instanceof Error ? err.message : "Failed to load picks."),
    );
  }, [onError, reload]);

  const openPicks = picks.filter(
    (entry) => entry.status !== "cancelled" && entry.status !== "staged",
  );

  async function advancePick(code: string) {
    if (!canMutate) {
      onError("You cannot mutate picks.");
      return;
    }
    const sku = findSkuByBarcode(skus, code);
    if (!sku) {
      onError("Unknown barcode.");
      return;
    }
    const pick = openPicks.find(
      (entry) =>
        entry.sku_id === sku.id || entry.lines.some((line) => line.sku_id === sku.id),
    );
    if (!pick) {
      onError("No open sales-order pick for that SKU.");
      return;
    }
    setSubmitting(true);
    try {
      if (pick.status === "draft") {
        const confirmed = await confirmPick(pick.id, pick.needs_confirm);
        onSuccess(`Confirmed ${confirmed.pick_number}. Scan again to stage.`);
      } else if (pick.status === "confirmed") {
        const staged = await completePick(pick.id);
        onSuccess(`${staged.pick_number} is ${staged.status}.`);
      } else {
        onSuccess(`${pick.pick_number} is ${pick.status}.`);
      }
      setBarcode("");
      await reload();
    } catch (err) {
      onError(err instanceof ApiError ? err.message : "Could not update pick.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Stack gap={5}>
      <WmsScanField
        id="wms-pick-scan"
        labelText="Scan SKU"
        value={barcode}
        onChange={setBarcode}
        onSubmit={(code) => void advancePick(code)}
        disabled={!canMutate || submitting}
      />
      {openPicks.length === 0 ? (
        <p className="cds--type-body-01">No open sales-order picks.</p>
      ) : (
        openPicks.map((pick) => (
          <div key={pick.id} className="vellano-wms-line-card">
            <strong>{pick.pick_number}</strong>
            <p className="cds--type-body-01">
              {pick.sku_our_ref || pick.lines[0]?.sku_our_ref || "Item"} · {pick.status}
            </p>
          </div>
        ))
      )}
      <Link href="/picks">Full picks page</Link>
    </Stack>
  );
}

function PackTab({
  canMutate,
  skus,
  onError,
  onSuccess,
}: FulfillmentTabProps & { skus: Sku[] }) {
  const [deliveries, setDeliveries] = useState<Delivery[]>([]);
  const [barcode, setBarcode] = useState("");
  const [cartonCount, setCartonCount] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const reload = useCallback(async () => {
    const page = await listDeliveries({ status: "draft", limit: 50 });
    const details = await Promise.all(page.items.map((item) => getDelivery(item.id)));
    setDeliveries(details);
  }, []);

  useEffect(() => {
    void reload().catch((err) =>
      onError(err instanceof Error ? err.message : "Failed to load deliveries."),
    );
  }, [onError, reload]);

  async function packFromScan(code: string) {
    if (!canMutate) {
      onError("You cannot pack deliveries.");
      return;
    }
    const sku = findSkuByBarcode(skus, code);
    const match = sku
      ? deliveries.find((entry) => entry.lines.some((line) => line.sku_id === sku.id))
      : deliveries.find((entry) =>
          entry.lines.some((line) => line.description.toLowerCase().includes(code.trim().toLowerCase())),
        );
    if (!match) {
      onError("No draft delivery line for that scan.");
      return;
    }
    const cartons = parsePositiveInt(cartonCount);
    setSubmitting(true);
    try {
      await packDelivery(match.id, cartons ?? undefined);
      onSuccess(`Packed ${match.delivery_number}.`);
      setBarcode("");
      await reload();
    } catch (err) {
      onError(err instanceof ApiError ? err.message : "Could not pack delivery.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Stack gap={5}>
      <WmsScanField
        id="wms-pack-scan"
        labelText="Scan into delivery"
        value={barcode}
        onChange={setBarcode}
        onSubmit={(code) => void packFromScan(code)}
        disabled={!canMutate || submitting}
      />
      <TextInput
        id="wms-carton-count"
        labelText="Carton count (optional)"
        value={cartonCount}
        onChange={(event) => setCartonCount(event.target.value)}
      />
      {deliveries.length === 0 ? (
        <p className="cds--type-body-01">No draft deliveries to pack.</p>
      ) : (
        deliveries.map((entry) => (
          <div key={entry.id} className="vellano-wms-line-card">
            <strong>{entry.delivery_number}</strong>
            <p className="cds--type-body-01">
              {entry.customer_name} · {entry.lines.length} lines
            </p>
          </div>
        ))
      )}
      <Link href="/deliveries">Full deliveries page</Link>
    </Stack>
  );
}

function DeliverTab({ canMutate, onError, onSuccess }: FulfillmentTabProps) {
  const [deliveries, setDeliveries] = useState<Delivery[]>([]);
  const [tracking, setTracking] = useState("");
  const [carrier, setCarrier] = useState("");
  const [submitting, setSubmitting] = useState<string | null>(null);

  const reload = useCallback(async () => {
    const [packed, loaded] = await Promise.all([
      listDeliveries({ status: "packed", limit: 50 }),
      listDeliveries({ status: "loaded", limit: 50 }),
    ]);
    const details = await Promise.all(
      [...packed.items, ...loaded.items].map((item) => getDelivery(item.id)),
    );
    setDeliveries(details);
  }, []);

  useEffect(() => {
    void reload().catch((err) =>
      onError(err instanceof Error ? err.message : "Failed to load deliveries."),
    );
  }, [onError, reload]);

  async function handleLoad(id: string) {
    if (!canMutate) {
      onError("You cannot load deliveries.");
      return;
    }
    setSubmitting(id);
    try {
      const row = await loadDelivery(id);
      onSuccess(`Loaded ${row.delivery_number}.`);
      await reload();
    } catch (err) {
      onError(err instanceof ApiError ? err.message : "Could not load delivery.");
    } finally {
      setSubmitting(null);
    }
  }

  async function handleComplete(id: string) {
    if (!canMutate) {
      onError("You cannot complete deliveries.");
      return;
    }
    setSubmitting(id);
    try {
      if (tracking.trim() || carrier.trim()) {
        await updateDeliveryTracking(id, {
          tracking_number: tracking.trim() || undefined,
          carrier: carrier.trim() || undefined,
        });
      }
      const row = await completeDelivery(id, {
        tracking_number: tracking.trim() || undefined,
        carrier: carrier.trim() || undefined,
      });
      onSuccess(`Delivered ${row.delivery_number}.`);
      setTracking("");
      setCarrier("");
      await reload();
    } catch (err) {
      onError(err instanceof ApiError ? err.message : "Could not complete delivery.");
    } finally {
      setSubmitting(null);
    }
  }

  return (
    <Stack gap={5}>
      <TextInput
        id="wms-tracking"
        labelText="Tracking number"
        value={tracking}
        onChange={(event) => setTracking(event.target.value)}
      />
      <TextInput
        id="wms-carrier"
        labelText="Carrier"
        value={carrier}
        onChange={(event) => setCarrier(event.target.value)}
      />
      {deliveries.length === 0 ? (
        <p className="cds--type-body-01">No packed or loaded deliveries.</p>
      ) : (
        deliveries.map((entry) => (
          <div key={entry.id} className="vellano-wms-line-card">
            <strong>{entry.delivery_number}</strong>
            <p className="cds--type-body-01">
              {entry.customer_name} · {entry.status}
            </p>
            {entry.status === "packed" ? (
              <Button
                size="sm"
                disabled={submitting !== null}
                onClick={() => void handleLoad(entry.id)}
              >
                {submitting === entry.id ? "Loading…" : "Load"}
              </Button>
            ) : (
              <Button
                size="sm"
                disabled={submitting !== null}
                onClick={() => void handleComplete(entry.id)}
              >
                {submitting === entry.id ? "Saving…" : "Mark delivered"}
              </Button>
            )}
          </div>
        ))
      )}
      <Link href="/deliveries">Full deliveries page</Link>
    </Stack>
  );
}
