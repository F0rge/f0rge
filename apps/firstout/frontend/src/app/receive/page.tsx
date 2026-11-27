"use client";

import { PageLoading } from "@/components/page-loading";
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
  Tag,
} from "@carbon/react";
import { useRouter, useSearchParams } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Suspense, useEffect, useState } from "react";
import { SkuLink } from "@/components/sku-link";

import { LocationBinFields } from "@/components/bin-select";
import { useLocationBins } from "@/hooks/use-location-bins";
import {
  ApiError,
  PO_STATUS_LABELS,
  canReceive,
  getPurchaseOrder,
  getSettings,
  isActiveLocation,
  listInventory,
  listLocations,
  listPurchaseOrders,
  listSkus,
  receivePurchaseOrder,
} from "@/lib/api";
import { optionalMovementBinId } from "@/lib/bin-helpers";
import { formatExpectedCartons } from "@/lib/carton-helpers";
import { usePageError } from "@/hooks/use-page-error";
import { useAuth } from "@/lib/auth";
import { formatQuantity } from "@/lib/quantity";

function ReceivePageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { user } = useAuth();
  const canRecv = canReceive(user);
  const [poId, setPoId] = useState("");
  // null until the user picks; then their choice wins while it is still an active location.
  const [chosenLocationId, setLocationId] = useState<string | null>(null);
  const [binId, setBinId] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [success, setSuccess] = useState<string | null>(null);
  const client = useQueryClient();
  const dataQuery = useQuery({
    queryKey: ["receive"],
    queryFn: async () => {
      const [orderData, locationData, inventoryData, skuData, settingsData] = await Promise.all([
        listPurchaseOrders({ status: "landed", limit: 100 }),
        listLocations(),
        listInventory(),
        listSkus({ lifecycle: "all" }),
        getSettings(),
      ]);
      return {
        orders: orderData.items.filter((order) => !order.is_archive),
        locations: locationData.filter(isActiveLocation),
        inventory: inventoryData,
        skus: skuData,
        defaultReceiveLocationId: settingsData.default_receive_location_id,
      };
    },
    enabled: Boolean(user),
  });
  const orders = dataQuery.data?.orders ?? [];
  const locations = dataQuery.data?.locations ?? [];
  const inventory = dataQuery.data?.inventory ?? [];
  const skus = dataQuery.data?.skus ?? [];
  const defaultReceiveLocationId = dataQuery.data?.defaultReceiveLocationId ?? null;
  const locationId =
    chosenLocationId !== null && (chosenLocationId === "" || locations.some((entry) => entry.id === chosenLocationId))
      ? chosenLocationId
      : defaultReceiveLocationId && locations.some((entry) => entry.id === defaultReceiveLocationId)
        ? defaultReceiveLocationId
        : "";
  const loading = dataQuery.isFetching;
  const { error, setError } = usePageError(dataQuery.error, "Failed to load receive data.");

  useEffect(() => {
    const prefilled = searchParams.get("po");
    if (prefilled) {
      setPoId(prefilled);
    }
  }, [searchParams]);

  const { activeBins, defaultBinId } = useLocationBins(locationId);

  useEffect(() => {
    setBinId(defaultBinId);
  }, [locationId, defaultBinId]);

  const selectedPoSummary = orders.find((entry) => entry.id === poId);
  const poDetailQuery = useQuery({
    queryKey: ["purchase-orders", "detail", poId],
    queryFn: () => getPurchaseOrder(poId),
    enabled: Boolean(poId),
  });
  const selectedPoDetail = (poId && poDetailQuery.data) || null;
  const formValid = Boolean(selectedPoSummary && !selectedPoSummary.is_archive && locationId);

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
        bin_id: optionalMovementBinId(binId, defaultBinId),
      });
      const po = orders.find((entry) => entry.id === poId);
      const location = locations.find((entry) => entry.id === locationId);
      setSuccess(
        `Received ${po?.po_number ?? "PO"} into ${location?.name ?? "location"}. Inventory updated.`,
      );
      setPoId("");
      setBinId("");
      setLocationId(null);
      await client.invalidateQueries({ queryKey: ["receive"] });
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
        <PageLoading kind="form" label="Loading receiving options…" fields={["Purchase order", "Location"]} />
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
          {selectedPoSummary && selectedPoSummary.status !== "landed" ? (
            <InlineNotification
              kind="info"
              title="Not landed"
              subtitle="This PO is not landed yet. Receive will fail until costs are landed."
              hideCloseButton
              lowContrast
            />
          ) : null}
          {selectedPoDetail && selectedPoSummary?.status === "landed" ? (
            <p className="cds--type-body-01">
              {formatExpectedCartons(selectedPoDetail, skus)}
            </p>
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
          <LocationBinFields
            idPrefix="receive"
            locationId={locationId}
            bins={activeBins}
            value={binId}
            onChange={setBinId}
            includeScan
          />
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
        {loading ? (
          <PageLoading
            label="Loading inventory…"
            title="Inventory"
            description="On-hand after receive"
            columns={["Our ref", "Name", "On order", "On hand", "Sellable", "Unit cost ZAR"]}
          />
        ) : inventory.length === 0 ? (
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
                    <TableCell><SkuLink id={entry.sku_id} context={{ ids: inventory.map((item) => item.sku_id), label: "Inventory" }}>{entry.our_ref}</SkuLink></TableCell>
                    <TableCell>{entry.name}{entry.is_archived && <Tag type="gray" size="sm">Archived</Tag>}</TableCell>
                    <TableCell>{formatQuantity(entry.on_order)}</TableCell>
                    <TableCell>{formatQuantity(entry.on_hand)}</TableCell>
                    <TableCell>{entry.sellable ? "Yes" : "Not sellable"}</TableCell>
                    <TableCell>{entry.unit_cost_zar ?? "—"}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        )}
      </div>

      {selectedPoSummary?.status === "landed" ? (
        <Button
          kind="ghost"
          size="sm"
          onClick={() => router.push(`/purchase-orders/${selectedPoSummary.id}`)}
        >
          View PO detail
        </Button>
      ) : null}
    </Stack>
  );
}

function ReceiveRouteLoading() {
  return (
    <Stack gap={6}>
      <div>
        <h1 className="cds--type-productive-heading-04">Receive</h1>
        <p className="cds--type-body-01">
          Receive a landed purchase order into an active location. PO must be landed before receive succeeds.
        </p>
      </div>
      <PageLoading kind="form" label="Loading receiving options…" fields={["Purchase order", "Location"]} />
      <div>
        <h2 className="cds--type-productive-heading-03">Current inventory</h2>
        <PageLoading label="Loading inventory…" title="Inventory" description="On-hand after receive"
          columns={["Our ref", "Name", "On order", "On hand", "Sellable", "Unit cost ZAR"]} />
      </div>
    </Stack>
  );
}

export default function ReceivePage() {
  return (
    <Suspense fallback={<ReceiveRouteLoading />}>
      <ReceivePageContent />
    </Suspense>
  );
}
