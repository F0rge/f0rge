"use client";

import {
  Button,
  ButtonSet,
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
  Tile,
} from "@carbon/react";
import { useCallback, useEffect, useMemo, useState } from "react";

import {
  ApiError,
  canUseTill,
  computeInvoicePreview,
  createTillSale,
  downloadInvoicePdf,
  formatZarAmount,
  isActiveLocation,
  listInventory,
  listLocations,
  listSkus,
  type InventorySku,
  type Location,
  type Sku,
  type TillSaleResult,
  type TillTender,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";

const SELLER = {
  name: "Vellano",
  address: "Kramerville, Johannesburg, South Africa",
  vat: "4123456789",
};

const VAT_RATE_LABEL = "15%";

export default function TillPage() {
  const { user } = useAuth();
  const canSell = canUseTill(user?.role);
  const [locations, setLocations] = useState<Location[]>([]);
  const [skus, setSkus] = useState<Sku[]>([]);
  const [inventory, setInventory] = useState<InventorySku[]>([]);
  const [locationId, setLocationId] = useState("");
  const [skuId, setSkuId] = useState("");
  const [qty, setQty] = useState<number | "">(1);
  const [tender, setTender] = useState<TillTender>("cash");
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastSale, setLastSale] = useState<TillSaleResult | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [locationData, skuData, inventoryData] = await Promise.all([
        listLocations(),
        listSkus(),
        listInventory(),
      ]);
      const showrooms = locationData.filter(
        (loc) => isActiveLocation(loc) && loc.type === "showroom",
      );
      setLocations(showrooms);
      setSkus(skuData);
      setInventory(inventoryData);
      if (!locationId && showrooms.length > 0) {
        setLocationId(showrooms[0].id);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load till data.");
    } finally {
      setLoading(false);
    }
  }, [locationId]);

  useEffect(() => {
    if (user) {
      void loadData();
    }
  }, [user, loadData]);

  const inventoryBySku = useMemo(
    () => new Map(inventory.map((entry) => [entry.sku_id, entry])),
    [inventory],
  );

  const selectedSku = skus.find((sku) => sku.id === skuId);
  const selectedInventory = skuId ? inventoryBySku.get(skuId) : undefined;
  const floorOnHand =
    selectedInventory?.locations.find((loc) => loc.location_id === locationId)?.on_hand ?? 0;

  const skuOptions = skus.filter((sku) => {
    if (!locationId || !sku.retail_ex_vat) {
      return false;
    }
    const row = inventoryBySku.get(sku.id);
    if (!row) {
      return false;
    }
    const atLocation = row.locations.find((loc) => loc.location_id === locationId);
    return (atLocation?.on_hand ?? 0) > 0;
  });

  const numericQty = typeof qty === "number" ? qty : 0;
  const unitExVat = selectedSku?.retail_ex_vat ? Number(selectedSku.retail_ex_vat) : 0;
  const preview = computeInvoicePreview(unitExVat * numericQty);

  const formValid =
    canSell &&
    locationId &&
    skuId &&
    numericQty > 0 &&
    numericQty <= floorOnHand &&
    unitExVat > 0;

  async function handleSale(selectedTender: TillTender) {
    if (!formValid) {
      return;
    }
    setSubmitting(true);
    setError(null);
    setLastSale(null);
    try {
      const result = await createTillSale({
        location_id: locationId,
        lines: [{ sku_id: skuId, qty: numericQty }],
        tender: selectedTender,
      });
      setLastSale(result);
      setTender(selectedTender);
      await loadData();
    } catch (err) {
      const message =
        err instanceof ApiError
          ? err.message
          : err instanceof Error
            ? err.message
            : "Sale failed.";
      setError(message);
    } finally {
      setSubmitting(false);
    }
  }

  if (!canSell) {
    return (
      <Stack gap={5}>
        <h1>Till</h1>
        <InlineNotification
          kind="error"
          title="Access denied"
          subtitle="Only till and owner roles can process showroom sales."
          hideCloseButton
          lowContrast
        />
      </Stack>
    );
  }

  return (
    <Stack gap={6}>
      <div>
        <h1>Till</h1>
        <p>Process showroom sales with cash or card payment recording.</p>
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
        <p>Loading…</p>
      ) : (
        <Tile>
          <Stack gap={5}>
            <Select
              id="till-location"
              labelText="Showroom"
              value={locationId}
              onChange={(event) => {
                setLocationId(event.target.value);
                setSkuId("");
              }}
            >
              <SelectItem value="" text="Select showroom" />
              {locations.map((loc) => (
                <SelectItem key={loc.id} value={loc.id} text={loc.name} />
              ))}
            </Select>

            <Select
              id="till-sku"
              labelText="SKU"
              value={skuId}
              onChange={(event) => setSkuId(event.target.value)}
              disabled={!locationId}
            >
              <SelectItem value="" text="Select SKU" />
              {skuOptions.map((sku) => (
                <SelectItem
                  key={sku.id}
                  value={sku.id}
                  text={`${sku.our_ref} — ${sku.name}`}
                />
              ))}
            </Select>

            <NumberInput
              id="till-qty"
              label="Quantity"
              min={1}
              max={floorOnHand || undefined}
              value={qty}
              onChange={(_, { value }) => {
                if (value === "") {
                  setQty("");
                } else {
                  setQty(typeof value === "number" ? value : Number(value));
                }
              }}
              helperText={
                skuId && locationId
                  ? `${floorOnHand} on hand at selected showroom`
                  : undefined
              }
              disabled={!skuId}
            />

            {selectedSku && numericQty > 0 ? (
              <TableContainer title="Sale preview">
                <Table size="sm">
                  <TableHead>
                    <TableRow>
                      <TableHeader>Description</TableHeader>
                      <TableHeader>Qty</TableHeader>
                      <TableHeader>Unit ex VAT</TableHeader>
                      <TableHeader>Ex VAT</TableHeader>
                      <TableHeader>VAT ({VAT_RATE_LABEL})</TableHeader>
                      <TableHeader>Inc VAT</TableHeader>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    <TableRow>
                      <TableCell>{selectedSku.name}</TableCell>
                      <TableCell>{numericQty}</TableCell>
                      <TableCell>{formatZarAmount(selectedSku.retail_ex_vat)}</TableCell>
                      <TableCell>{formatZarAmount(String(unitExVat * numericQty))}</TableCell>
                      <TableCell>{formatZarAmount(String(preview.vat))}</TableCell>
                      <TableCell>{formatZarAmount(String(preview.totalIncVat))}</TableCell>
                    </TableRow>
                  </TableBody>
                </Table>
              </TableContainer>
            ) : null}

            <ButtonSet>
              <Button
                kind="primary"
                disabled={!formValid || submitting}
                onClick={() => void handleSale("cash")}
              >
                Take cash
              </Button>
              <Button
                kind="secondary"
                disabled={!formValid || submitting}
                onClick={() => void handleSale("card")}
              >
                Take card
              </Button>
            </ButtonSet>
          </Stack>
        </Tile>
      )}

      {lastSale ? (
        <Tile className="vellano-tax-invoice">
          <Stack gap={5}>
            <div className="vellano-tax-invoice__header">
              <h2>Tax invoice {lastSale.invoice_number}</h2>
              <p>
                Payment {lastSale.payment_number} — {lastSale.tender}
              </p>
            </div>

            <div className="vellano-tax-invoice__parties">
              <div>
                <strong>Seller</strong>
                <p>{SELLER.name}</p>
                <p>{SELLER.address}</p>
                <p>VAT no. {SELLER.vat}</p>
              </div>
              <div>
                <strong>Buyer</strong>
                <p>Walk-in customer</p>
              </div>
            </div>

            <TableContainer>
              <Table size="sm">
                <TableHead>
                  <TableRow>
                    <TableHeader>Description</TableHeader>
                    <TableHeader>Qty</TableHeader>
                    <TableHeader>Ex VAT</TableHeader>
                    <TableHeader>VAT</TableHeader>
                    <TableHeader>Inc VAT</TableHeader>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {lastSale.lines.map((line) => (
                    <TableRow key={line.id}>
                      <TableCell>{line.description}</TableCell>
                      <TableCell>{line.qty}</TableCell>
                      <TableCell>{formatZarAmount(line.ex_vat)}</TableCell>
                      <TableCell>{formatZarAmount(line.vat_amount)}</TableCell>
                      <TableCell>{formatZarAmount(line.inc_vat)}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>

            <div>
              <p>Subtotal ex VAT: {formatZarAmount(lastSale.subtotal_ex_vat)}</p>
              <p>VAT ({VAT_RATE_LABEL}): {formatZarAmount(lastSale.vat_amount)}</p>
              <p>
                <strong>Total inc VAT: {formatZarAmount(lastSale.total_inc_vat)}</strong>
              </p>
              <p>
                Floor stock remaining at {lastSale.location.location_name}:{" "}
                {lastSale.location.on_hand}
              </p>
            </div>

            <ButtonSet>
              <Button
                kind="tertiary"
                onClick={() => void downloadInvoicePdf(lastSale.invoice_id, lastSale.invoice_number)}
              >
                Download PDF
              </Button>
            </ButtonSet>
          </Stack>
        </Tile>
      ) : null}
    </Stack>
  );
}
