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
} from "@carbon/react";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useState } from "react";

import {
  ApiError,
  PO_STATUS_LABELS,
  canReceive,
  isActiveLocation,
  listInventory,
  listLocations,
  listPurchaseOrders,
  receivePurchaseOrder,
  type InventorySku,
  type Location,
  type PurchaseOrder,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";

function ReceivePageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { user } = useAuth();
  const canRecv = canReceive(user?.role);
  const [orders, setOrders] = useState<PurchaseOrder[]>([]);
  const [locations, setLocations] = useState<Location[]>([]);
  const [inventory, setInventory] = useState<InventorySku[]>([]);
  const [poId, setPoId] = useState("");
  const [locationId, setLocationId] = useState("");
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [orderData, locationData, inventoryData] = await Promise.all([
        listPurchaseOrders(),
        listLocations(),
        listInventory(),
      ]);
      setOrders(orderData);
      setLocations(locationData.filter(isActiveLocation));
      setInventory(inventoryData);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load receive data.");
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
    const prefilled = searchParams.get("po");
    if (prefilled) {
      setPoId(prefilled);
    }
  }, [searchParams]);

  const selectedPo = orders.find((entry) => entry.id === poId);
  const formValid = poId && locationId;

  async function handleReceive() {
    if (!canRecv || !formValid) {
      return;
    }
    setSubmitting(true);
    setError(null);
    setSuccess(null);
    try {
      await receivePurchaseOrder({
        purchase_order_id: poId,
        location_id: locationId,
      });
      const po = orders.find((entry) => entry.id === poId);
      const location = locations.find((entry) => entry.id === locationId);
      setSuccess(
        `Received ${po?.po_number ?? "PO"} into ${location?.name ?? "location"}. Inventory updated.`,
      );
      setPoId("");
      setLocationId("");
      await loadData();
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setError(err.message);
      } else {
        setError(err instanceof Error ? err.message : "Failed to receive purchase order.");
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Stack gap={6}>
      <div>
        <h1 className="cds--type-productive-heading-04">Receive</h1>
        <p className="cds--type-body-01">
          Receive a landed purchase order into an active location. PO must be landed before receive
          succeeds.
        </p>
      </div>

      {!canRecv ? (
        <InlineNotification
          kind="warning"
          title="Permission required"
          subtitle="Only owner and warehouse roles can receive stock."
          hideCloseButton
          lowContrast
        />
      ) : null}

      {success ? (
        <InlineNotification
          kind="success"
          title="Received"
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
            id="receive-po"
            labelText="Purchase order"
            value={poId}
            onChange={(event) => setPoId(event.target.value)}
          >
            <SelectItem value="" text="Select a purchase order" />
            {orders.map((entry) => (
              <SelectItem
                key={entry.id}
                value={entry.id}
                text={`${entry.po_number} — ${entry.supplier_name} (${PO_STATUS_LABELS[entry.status]})`}
              />
            ))}
          </Select>
          {selectedPo && selectedPo.status !== "landed" ? (
            <InlineNotification
              kind="info"
              title="Not landed"
              subtitle="This PO is not landed yet. Receive will fail until costs are landed."
              hideCloseButton
              lowContrast
            />
          ) : null}
          <Select
            id="receive-location"
            labelText="Location"
            value={locationId}
            onChange={(event) => setLocationId(event.target.value)}
          >
            <SelectItem value="" text="Select a location" />
            {locations.map((entry) => (
              <SelectItem key={entry.id} value={entry.id} text={entry.name} />
            ))}
          </Select>
          {canRecv ? (
            <Button
              disabled={submitting || !formValid}
              onClick={() => void handleReceive()}
            >
              {submitting ? "Receiving…" : "Receive"}
            </Button>
          ) : null}
        </Stack>
      )}

      <div>
        <h2 className="cds--type-productive-heading-03">Current inventory</h2>
        {loading ? null : inventory.length === 0 ? (
          <p className="cds--type-body-01">No inventory records yet.</p>
        ) : (
          <TableContainer title="Inventory" description="On-hand after receive">
            <Table>
              <TableHead>
                <TableRow>
                  <TableHeader>Our ref</TableHeader>
                  <TableHeader>Name</TableHeader>
                  <TableHeader>On order</TableHeader>
                  <TableHeader>On hand</TableHeader>
                  <TableHeader>Sellable</TableHeader>
                  <TableHeader>Unit cost ZAR</TableHeader>
                </TableRow>
              </TableHead>
              <TableBody>
                {inventory.map((entry) => (
                  <TableRow key={entry.sku_id}>
                    <TableCell>{entry.our_ref}</TableCell>
                    <TableCell>{entry.name}</TableCell>
                    <TableCell>{entry.on_order}</TableCell>
                    <TableCell>{entry.on_hand}</TableCell>
                    <TableCell>{entry.sellable ? "Yes" : "Not sellable"}</TableCell>
                    <TableCell>{entry.unit_cost_zar ?? "—"}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        )}
      </div>

      {selectedPo?.status === "landed" ? (
        <Button kind="ghost" size="sm" onClick={() => router.push(`/purchase-orders/${selectedPo.id}`)}>
          View PO detail
        </Button>
      ) : null}
    </Stack>
  );
}

export default function ReceivePage() {
  return (
    <Suspense fallback={<p className="cds--type-body-01">Loading…</p>}>
      <ReceivePageContent />
    </Suspense>
  );
}
