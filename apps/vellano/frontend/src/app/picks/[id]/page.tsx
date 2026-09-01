"use client";

import {
  Button,
  Checkbox,
  InlineNotification,
  Select,
  SelectItem,
  Stack,
  Tag,
} from "@carbon/react";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";

import { PickMatrix } from "@/components/pick-matrix";
import {
  ApiError,
  canMutatePicks,
  cancelPick,
  completePick,
  confirmPick,
  downloadPickPdf,
  getPick,
  isActiveLocation,
  listLocations,
  previewPick,
  updatePick,
  type Location,
  type PickDocument,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";
import {
  PICK_STATUS_LABELS,
  allocationsPayload,
  canCancelPick,
  canCompletePick,
  canConfirmPick,
  firstWarehouseId,
  isConfirmSplitRequiredMessage,
  isPickEditable,
  onHandFromLines,
  onHandFromPreview,
  pickStatusTagType,
  qtyMapFromAllocations,
  qtyMapFromPreview,
  type PickQtyMap,
} from "@/lib/picks";

export default function PickDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const { user } = useAuth();
  const canMutate = canMutatePicks(user);
  const [pick, setPick] = useState<PickDocument | null>(null);
  const [locations, setLocations] = useState<Location[]>([]);
  const [qty, setQty] = useState<PickQtyMap>({});
  const [onHand, setOnHand] = useState<Record<string, Record<string, number>>>({});
  const [needsConfirm, setNeedsConfirm] = useState(false);
  const [qtyShort, setQtyShort] = useState(false);
  const [ackSplit, setAckSplit] = useState(false);
  const [confirmSplitRequired, setConfirmSplitRequired] = useState(false);
  const [stagingLocationId, setStagingLocationId] = useState("");
  const [collectFromShowroom, setCollectFromShowroom] = useState(false);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const activeLocations = useMemo(() => locations.filter(isActiveLocation), [locations]);

  const applyPick = useCallback((next: PickDocument, suggested?: PickQtyMap) => {
    setPick(next);
    setNeedsConfirm(next.needs_confirm);
    setQtyShort(next.qty_short);
    setCollectFromShowroom(next.collect_from_showroom);
    const fromDoc = qtyMapFromAllocations(next.lines);
    const hasAllocations = next.lines.some((line) =>
      line.allocations.some((allocation) => allocation.qty > 0),
    );
    setQty(hasAllocations || !suggested ? fromDoc : suggested);
    const fromDocOnHand = onHandFromLines(next.lines);
    if (Object.keys(fromDocOnHand).length > 0) {
      setOnHand((current) => ({ ...fromDocOnHand, ...current }));
    }
    if (next.staging_location_id) {
      setStagingLocationId(next.staging_location_id);
    }
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [loaded, locationData] = await Promise.all([getPick(params.id), listLocations()]);
      const active = locationData.filter(isActiveLocation);
      setLocations(active);
      let doc = loaded;
      let suggested: PickQtyMap | undefined;
      try {
        const preview = await previewPick({ sku_id: doc.sku_id, qty: doc.qty });
        setOnHand(onHandFromPreview(preview));
        setNeedsConfirm(doc.needs_confirm || preview.needs_confirm);
        setQtyShort(doc.qty_short || preview.qty_short);
        suggested = qtyMapFromPreview(preview);
        if (doc.lines.length === 0 && preview.lines.length > 0) {
          doc = {
            ...doc,
            lines: preview.lines.map((line) => ({
              sku_id: line.sku_id,
              sku_our_ref: line.sku_our_ref,
              sku_name: line.sku_name,
              qty_needed: line.qty_needed,
              allocations: line.locations.map((location) => ({
                location_id: location.location_id,
                location_name: location.location_name,
                on_hand: location.on_hand,
                qty: location.suggested_qty,
              })),
            })),
          };
        }
      } catch {
        setOnHand({});
      }
      applyPick(doc, suggested);
      setStagingLocationId((current) => current || doc.staging_location_id || firstWarehouseId(active));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load pick.");
    } finally {
      setLoading(false);
    }
  }, [applyPick, params.id]);

  useEffect(() => {
    if (user && params.id) {
      void load();
    }
  }, [user, params.id, load]);

  const readOnly = !canMutate || !pick || !isPickEditable(pick.status);

  function handleQtyChange(skuId: string, locationId: string, amount: number) {
    setQty((current) => ({
      ...current,
      [skuId]: { ...current[skuId], [locationId]: amount },
    }));
  }

  async function handleSave() {
    if (!pick || readOnly) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const updated = await updatePick(pick.id, allocationsPayload(pick.lines, qty));
      applyPick(updated);
      setNotice("Allocations saved.");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to save allocations.");
    } finally {
      setBusy(false);
    }
  }

  async function handleConfirm() {
    if (!pick || !canMutate || !canConfirmPick(pick.status)) {
      return;
    }
    const requireAck = needsConfirm || confirmSplitRequired;
    if (requireAck && !ackSplit) {
      setError("Acknowledge the split before confirming.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const updated = await confirmPick(pick.id, requireAck && ackSplit ? true : undefined);
      applyPick(updated);
      setConfirmSplitRequired(false);
      setNotice(`${updated.pick_number || "Pick"} confirmed.`);
    } catch (err) {
      if (err instanceof ApiError && err.status === 409 && isConfirmSplitRequiredMessage(err.message)) {
        setConfirmSplitRequired(true);
        setNeedsConfirm(true);
        setError(err.message);
      } else {
        setError(err instanceof ApiError ? err.message : "Failed to confirm pick.");
      }
    } finally {
      setBusy(false);
    }
  }

  async function handleComplete() {
    if (!pick || !canMutate || !canCompletePick(pick.status)) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const updated = await completePick(pick.id, {
        ...(stagingLocationId ? { staging_location_id: stagingLocationId } : {}),
        collect_from_showroom: collectFromShowroom,
      });
      applyPick(updated);
      setNotice(`${updated.pick_number || "Pick"} completed.`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to complete pick.");
    } finally {
      setBusy(false);
    }
  }

  async function handleCancel() {
    if (!pick || !canMutate || !canCancelPick(pick.status)) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const updated = await cancelPick(pick.id);
      applyPick(updated);
      setNotice(`${updated.pick_number || "Pick"} cancelled.`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to cancel pick.");
    } finally {
      setBusy(false);
    }
  }

  async function handlePrint() {
    if (!pick) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await downloadPickPdf(pick.id, pick.pick_number || "pick");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to print pick slip.");
    } finally {
      setBusy(false);
    }
  }

  const showSplitBanner = needsConfirm || confirmSplitRequired;

  return (
    <Stack gap={6}>
      <div className="vellano-page-header">
        <div>
          <Button kind="ghost" size="sm" onClick={() => router.push("/picks")}>
            Back to picks
          </Button>
          <h1 className="cds--type-productive-heading-04">
            {pick?.pick_number || "Pick"}
          </h1>
          {pick ? (
            <p className="cds--type-body-01">
              {pick.sku_our_ref || pick.sku_id}
              {pick.sku_name ? ` — ${pick.sku_name}` : ""} × {pick.qty}
            </p>
          ) : null}
        </div>
        {pick ? (
          <Tag type={pickStatusTagType(pick.status)} size="md">
            {PICK_STATUS_LABELS[pick.status]}
          </Tag>
        ) : null}
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
      {notice ? (
        <InlineNotification
          kind="info"
          title="Picks"
          subtitle={notice}
          onCloseButtonClick={() => setNotice(null)}
          lowContrast
        />
      ) : null}
      {showSplitBanner ? (
        <InlineNotification
          kind="warning"
          title="Split pick"
          subtitle="This kit is split across locations. Confirm only after you acknowledge the split."
          hideCloseButton
          lowContrast
        />
      ) : null}
      {qtyShort ? (
        <InlineNotification
          kind="error"
          title="Short pick"
          subtitle="Allocated quantity is short of what the kit needs."
          hideCloseButton
          lowContrast
        />
      ) : null}

      {loading || !pick ? (
        <p className="cds--type-body-01">{loading ? "Loading pick…" : "Pick not found."}</p>
      ) : (
        <Stack gap={6}>
          <PickMatrix
            locations={activeLocations}
            lines={pick.lines}
            onHand={onHand}
            qty={qty}
            onQtyChange={handleQtyChange}
            readOnly={readOnly}
          />

          {canMutate && isPickEditable(pick.status) ? (
            <Button kind="secondary" disabled={busy} onClick={() => void handleSave()}>
              Save allocations
            </Button>
          ) : null}

          {canMutate && canConfirmPick(pick.status) ? (
            <Stack gap={4}>
              {showSplitBanner ? (
                <Checkbox
                  id="pick-ack-split"
                  labelText="I acknowledge this split pick"
                  checked={ackSplit}
                  onChange={() => setAckSplit((current) => !current)}
                />
              ) : null}
              <Button
                kind="primary"
                disabled={busy || (showSplitBanner && !ackSplit)}
                onClick={() => void handleConfirm()}
              >
                Confirm pick
              </Button>
            </Stack>
          ) : null}

          <Stack gap={5}>
            <div className="vellano-catalogue-actions">
              <Button kind="tertiary" disabled={busy} onClick={() => void handlePrint()}>
                Print slip
              </Button>
              {canMutate && canCancelPick(pick.status) ? (
                <Button kind="danger--tertiary" disabled={busy} onClick={() => void handleCancel()}>
                  Cancel
                </Button>
              ) : null}
            </div>
            {canMutate && canCompletePick(pick.status) ? (
              <Stack gap={4}>
                <Select
                  id="pick-staging"
                  labelText="Staging location"
                  helperText="Defaults to the first warehouse location."
                  value={stagingLocationId}
                  onChange={(event) => setStagingLocationId(event.target.value)}
                >
                  <SelectItem value="" text="Select location" />
                  {activeLocations.map((location) => (
                    <SelectItem key={location.id} value={location.id} text={location.name} />
                  ))}
                </Select>
                <Checkbox
                  id="pick-collect-showroom"
                  labelText="Collect from showroom"
                  checked={collectFromShowroom}
                  onChange={() => setCollectFromShowroom((current) => !current)}
                />
                <Button kind="primary" disabled={busy} onClick={() => void handleComplete()}>
                  Complete
                </Button>
              </Stack>
            ) : null}
          </Stack>
        </Stack>
      )}
    </Stack>
  );
}
