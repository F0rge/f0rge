"use client";

import {
  Button,
  InlineNotification,
  Select,
  SelectItem,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableHeader,
  TableRow,
  TextInput,
} from "@carbon/react";
import { useCallback, useEffect, useState } from "react";

import {
  ADJUSTMENT_REASON_LABELS,
  ADJUSTMENT_REASONS,
  ADJUSTMENT_STATUS_LABELS,
  ApiError,
  canReceive,
  createAdjustment,
  getAdjustment,
  isActiveLocation,
  listAdjustments,
  listInventory,
  listLocations,
  listSkus,
  type Adjustment,
  type AdjustmentLine,
  type AdjustmentReason,
  type AdjustmentSummary,
  type InventorySku,
  type Location,
  type Sku,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";

import { AdjustmentDraft } from "./adjustment-draft";
import { AdjustmentView } from "./adjustment-view";

function formatDateTime(iso: string | undefined | null): string {
  if (!iso) {
    return "—";
  }
  return new Date(iso).toLocaleString("en-ZA");
}

function withLines(entry: Adjustment | AdjustmentSummary): Adjustment {
  return { ...entry, lines: entry.lines ?? [] };
}

function locationLabel(entry: AdjustmentSummary, locations: Location[]): string {
  return entry.location_name ?? locations.find((loc) => loc.id === entry.location_id)?.name ?? "—";
}

function historyDate(entry: AdjustmentSummary): string | undefined | null {
  return entry.completed_at ?? entry.cancelled_at ?? entry.created_at ?? entry.started_at;
}

export default function AdjustmentsPage() {
  const { user } = useAuth();
  const canMutate = canReceive(user);
  const [summaries, setSummaries] = useState<AdjustmentSummary[]>([]);
  const [locations, setLocations] = useState<Location[]>([]);
  const [skus, setSkus] = useState<Sku[]>([]);
  const [inventory, setInventory] = useState<InventorySku[]>([]);
  const [active, setActive] = useState<Adjustment | null>(null);
  const [viewing, setViewing] = useState<Adjustment | null>(null);
  const [locationId, setLocationId] = useState("");
  const [reason, setReason] = useState<AdjustmentReason | "">("");
  const [notes, setNotes] = useState("");
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [summaryData, locationData, skuData, inventoryData] = await Promise.all([
        listAdjustments(),
        listLocations(),
        listSkus(),
        listInventory(),
      ]);
      setSummaries(summaryData);
      setLocations(locationData.filter(isActiveLocation));
      setSkus(skuData);
      setInventory(inventoryData);
      const draftSummary = summaryData.find((entry) => entry.status === "draft");
      if (draftSummary) {
        setActive(withLines(await getAdjustment(draftSummary.id)));
        setViewing(null);
      } else {
        setActive(null);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load adjustments.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (user) {
      void load();
    }
  }, [user, load]);

  const history = summaries
    .filter((entry) => entry.status !== "draft")
    .slice()
    .sort((a, b) => (historyDate(b) ?? "").localeCompare(historyDate(a) ?? ""));

  async function handleStart() {
    if (!canMutate || !locationId || !reason) {
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const trimmedNotes = notes.trim();
      await createAdjustment({
        location_id: locationId,
        reason,
        ...(trimmedNotes ? { notes: trimmedNotes } : {}),
      });
      setLocationId("");
      setReason("");
      setNotes("");
      await load();
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setError(err.message);
        await load();
      } else {
        setError(err instanceof Error ? err.message : "Failed to start draft.");
      }
    } finally {
      setSubmitting(false);
    }
  }

  function handleLinesChanged(lines: AdjustmentLine[]) {
    setActive((current) => (current ? { ...current, lines } : current));
  }

  async function handleOpenCompleted(entry: AdjustmentSummary) {
    if (entry.status !== "completed" || active) {
      return;
    }
    setError(null);
    try {
      setViewing(withLines(await getAdjustment(entry.id)));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load adjustment.");
    }
  }

  return (
    <Stack gap={6}>
      {error ? (
        <InlineNotification
          kind="error"
          title="Error"
          subtitle={error}
          onCloseButtonClick={() => setError(null)}
          lowContrast
        />
      ) : null}

      <InlineNotification
        kind="info"
        title="GL impact"
        subtitle="Increases debit Inventory 1300 / credit Opening balances 3000; decreases debit COGS 5000 / credit Inventory 1300."
        hideCloseButton
        lowContrast
      />

      {loading ? (
        <p className="cds--type-body-01">Loading adjustments…</p>
      ) : active ? (
        <AdjustmentDraft
          key={active.id}
          adjustment={active}
          locationName={locationLabel(active, locations)}
          skus={skus}
          inventory={inventory}
          canMutate={canMutate}
          onLinesChanged={handleLinesChanged}
          onFinished={load}
          onError={setError}
        />
      ) : viewing ? (
        <AdjustmentView
          adjustment={viewing}
          locationName={locationLabel(viewing, locations)}
          inventory={inventory}
          onBack={() => setViewing(null)}
        />
      ) : (
        <Stack gap={6}>
          <div>
            <h1 className="cds--type-productive-heading-04">Stock Adjustment</h1>
            <p className="cds--type-body-01">
              Create an adjustment to correct on-hand inventory levels or write off damaged stock.
            </p>
          </div>

          {!canMutate ? (
            <InlineNotification
              kind="warning"
              title="Permission required"
              subtitle="Only owner and warehouse roles can start or complete an adjustment."
              hideCloseButton
              lowContrast
            />
          ) : (
            <Stack gap={5}>
              <Select
                id="adjustment-location"
                labelText="Location"
                value={locationId}
                onChange={(event) => setLocationId(event.target.value)}
                helperText={
                  locations.length === 0 ? "No active locations available" : undefined
                }
              >
                <SelectItem value="" text="Select a location" />
                {locations.map((entry) => (
                  <SelectItem key={entry.id} value={entry.id} text={entry.name} />
                ))}
              </Select>
              <Select
                id="adjustment-reason"
                labelText="Reason"
                value={reason}
                onChange={(event) => setReason(event.target.value as AdjustmentReason | "")}
              >
                <SelectItem value="" text="Select a reason" />
                {ADJUSTMENT_REASONS.map((entry) => (
                  <SelectItem key={entry} value={entry} text={ADJUSTMENT_REASON_LABELS[entry]} />
                ))}
              </Select>
              <TextInput
                id="adjustment-notes"
                labelText="Notes"
                placeholder="e.g., Found during Q3 audit, pallet damage..."
                value={notes}
                onChange={(event) => setNotes(event.target.value)}
              />
              <Button
                disabled={submitting || !locationId || !reason}
                onClick={() => void handleStart()}
              >
                {submitting ? "Starting…" : "Start draft"}
              </Button>
            </Stack>
          )}
        </Stack>
      )}

      {!loading && !active && !viewing && history.length === 0 ? (
        <InlineNotification
          kind="info"
          title="No adjustments"
          subtitle="No completed or cancelled adjustments yet."
          hideCloseButton
          lowContrast
        />
      ) : null}

      {!loading && history.length > 0 ? (
        <TableContainer title="History" description="Completed and cancelled adjustments">
          <Table>
            <TableHead>
              <TableRow>
                <TableHeader>Location</TableHeader>
                <TableHeader>Reason</TableHeader>
                <TableHeader>Status</TableHeader>
                <TableHeader>Date</TableHeader>
              </TableRow>
            </TableHead>
            <TableBody>
              {history.map((entry) => {
                const clickable = entry.status === "completed" && !active;
                return (
                  <TableRow
                    key={entry.id}
                    onClick={clickable ? () => void handleOpenCompleted(entry) : undefined}
                    style={clickable ? { cursor: "pointer" } : undefined}
                  >
                    <TableCell>{locationLabel(entry, locations)}</TableCell>
                    <TableCell>{ADJUSTMENT_REASON_LABELS[entry.reason]}</TableCell>
                    <TableCell>{ADJUSTMENT_STATUS_LABELS[entry.status]}</TableCell>
                    <TableCell>{formatDateTime(historyDate(entry))}</TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </TableContainer>
      ) : null}
    </Stack>
  );
}
