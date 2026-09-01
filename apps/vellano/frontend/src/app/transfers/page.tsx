"use client";

import {
  Button,
  InlineNotification,
  NumberInput,
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
} from "@carbon/react";
import { useCallback, useEffect, useMemo, useState } from "react";

import {
  ApiError,
  canTransfer,
  createTransfer,
  isActiveLocation,
  listInventory,
  listLocations,
  listSkus,
  type InventorySku,
  type Location,
  type Sku,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";

export default function TransfersPage() {
  const { user } = useAuth();
  const canXfer = canTransfer(user?.role);
  const [locations, setLocations] = useState<Location[]>([]);
  const [skus, setSkus] = useState<Sku[]>([]);
  const [inventory, setInventory] = useState<InventorySku[]>([]);
  const [fromLocationId, setFromLocationId] = useState("");
  const [toLocationId, setToLocationId] = useState("");
  const [skuId, setSkuId] = useState("");
  const [qty, setQty] = useState<number | "">(1);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [locationData, skuData, inventoryData] = await Promise.all([
        listLocations(),
        listSkus(),
        listInventory(),
      ]);
      setLocations(locationData.filter(isActiveLocation));
      setSkus(skuData);
      setInventory(inventoryData);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load transfer data.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (user) {
      void loadData();
    }
  }, [user, loadData]);

  const inventoryBySku = useMemo(
    () => new Map(inventory.map((entry) => [entry.sku_id, entry])),
    [inventory],
  );

  const selectedSkuInventory = skuId ? inventoryBySku.get(skuId) : undefined;
  const sourceOnHand =
    selectedSkuInventory?.locations.find((loc) => loc.location_id === fromLocationId)
      ?.on_hand ?? 0;

  const destinationOptions = locations.filter((loc) => loc.id !== fromLocationId);
  const sourceOptions = locations.filter((loc) => loc.id !== toLocationId);

  const skuOptions = skus.filter((sku) => {
    const row = inventoryBySku.get(sku.id);
    if (!fromLocationId || !row) {
      return false;
    }
    const atSource = row.locations.find((loc) => loc.location_id === fromLocationId);
    return (atSource?.on_hand ?? 0) > 0;
  });

  const numericQty = typeof qty === "number" ? qty : 0;
  const formValid =
    fromLocationId &&
    toLocationId &&
    skuId &&
    numericQty > 0 &&
    numericQty <= sourceOnHand;

  async function handleTransfer() {
    if (!canXfer || !formValid) {
      return;
    }
    setSubmitting(true);
    setError(null);
    setSuccess(null);
    try {
      const result = await createTransfer({
        from_location_id: fromLocationId,
        to_location_id: toLocationId,
        sku_id: skuId,
        qty: numericQty,
      });
      const fromName = result.from_location.location_name;
      const toName = result.to_location.location_name;
      setSuccess(
        `Transferred ${result.qty} × ${result.our_ref} from ${fromName} (${result.from_location.on_hand} on hand) to ${toName} (${result.to_location.on_hand} on hand).`,
      );
      setSkuId("");
      setQty(1);
      await loadData();
    } catch (err) {
      if (err instanceof ApiError && (err.status === 409 || err.status === 400)) {
        setError(err.message);
      } else {
        setError(err instanceof Error ? err.message : "Failed to transfer stock.");
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Stack gap={6}>
      <div>
        <h1 className="cds--type-productive-heading-04">Transfers</h1>
        <p className="cds--type-body-01">
          Move on-hand units between locations. Unit cost is unchanged on transfer. On-order stock
          cannot be transferred.
        </p>
      </div>

      {!canXfer ? (
        <InlineNotification
          kind="warning"
          title="Permission required"
          subtitle="Only owner and warehouse roles can transfer stock."
          hideCloseButton
          lowContrast
        />
      ) : null}

      {success ? (
        <InlineNotification
          kind="success"
          title="Transferred"
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
      ) : (
        <Stack gap={5}>
          <Select
            id="transfer-from"
            labelText="From location"
            value={fromLocationId}
            onChange={(event) => {
              setFromLocationId(event.target.value);
              setSkuId("");
            }}
          >
            <SelectItem value="" text="Select source location" />
            {sourceOptions.map((entry) => (
              <SelectItem key={entry.id} value={entry.id} text={entry.name} />
            ))}
          </Select>
          <Select
            id="transfer-to"
            labelText="To location"
            value={toLocationId}
            onChange={(event) => setToLocationId(event.target.value)}
          >
            <SelectItem value="" text="Select destination location" />
            {destinationOptions.map((entry) => (
              <SelectItem key={entry.id} value={entry.id} text={entry.name} />
            ))}
          </Select>
          <Select
            id="transfer-sku"
            labelText="SKU"
            value={skuId}
            onChange={(event) => setSkuId(event.target.value)}
            disabled={!fromLocationId}
            helperText={
              fromLocationId
                ? sourceOnHand > 0 && skuId
                  ? `${sourceOnHand} on hand at source`
                  : "Only SKUs with on-hand stock at the source are listed"
                : "Choose a source location first"
            }
          >
            <SelectItem value="" text="Select SKU" />
            {skuOptions.map((entry) => (
              <SelectItem
                key={entry.id}
                value={entry.id}
                text={`${entry.our_ref} — ${entry.name}`}
              />
            ))}
          </Select>
          <NumberInput
            id="transfer-qty"
            label="Quantity"
            min={1}
            value={qty}
            onChange={(_event, { value }) => {
              if (value === "") {
                setQty("");
              } else {
                setQty(Number(value));
              }
            }}
            invalid={numericQty > sourceOnHand && sourceOnHand > 0}
            invalidText={`Only ${sourceOnHand} available at source`}
            disabled={!skuId}
          />
          {canXfer ? (
            <Button disabled={submitting || !formValid} onClick={() => void handleTransfer()}>
              {submitting ? "Transferring…" : "Transfer"}
            </Button>
          ) : null}
        </Stack>
      )}

      <div>
        <h2 className="cds--type-productive-heading-03">On-hand by location</h2>
        {loading ? null : inventory.length === 0 ? (
          <p className="cds--type-body-01">No on-hand stock yet.</p>
        ) : (
          <TableContainer title="Inventory" description="Current balances after transfers">
            <Table>
              <TableHead>
                <TableRow>
                  <TableHeader>Our ref</TableHeader>
                  <TableHeader>Name</TableHeader>
                  <TableHeader>Location</TableHeader>
                  <TableHeader>On hand</TableHeader>
                  <TableHeader>Unit cost ZAR</TableHeader>
                </TableRow>
              </TableHead>
              <TableBody>
                {inventory.flatMap((entry) =>
                  entry.locations.length === 0
                    ? [
                        <TableRow key={`${entry.sku_id}-none`}>
                          <TableCell>{entry.our_ref}</TableCell>
                          <TableCell>{entry.name}</TableCell>
                          <TableCell>—</TableCell>
                          <TableCell>0</TableCell>
                          <TableCell>—</TableCell>
                        </TableRow>,
                      ]
                    : entry.locations.map((loc) => (
                        <TableRow key={`${entry.sku_id}-${loc.location_id}`}>
                          <TableCell>{entry.our_ref}</TableCell>
                          <TableCell>{entry.name}</TableCell>
                          <TableCell>{loc.location_name}</TableCell>
                          <TableCell>{loc.on_hand}</TableCell>
                          <TableCell>{loc.unit_cost_zar ?? "—"}</TableCell>
                        </TableRow>
                      )),
                )}
              </TableBody>
            </Table>
          </TableContainer>
        )}
      </div>
    </Stack>
  );
}
