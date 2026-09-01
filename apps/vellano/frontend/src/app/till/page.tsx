"use client";

import {
  Button,
  ButtonSet,
  Column,
  Grid,
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
import { Currency, TrashCan, Undo } from "@carbon/icons-react";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";

import {
  ApiError,
  canUseTill,
  computeInvoicePreview,
  createTillSale,
  downloadInvoicePdf,
  exVatToIncVat,
  formatPriceAmount,
  formatZarAmount,
  incVatToExVat,
  isActiveLocation,
  listInventory,
  listLocations,
  listSkus,
  roundHalfUp,
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

const TENDER_OPTIONS: { value: TillTender; label: string }[] = [
  { value: "card", label: "Card" },
  { value: "cash", label: "Cash" },
  { value: "deposit", label: "Deposit" },
];

type CartLine = {
  key: string;
  sku: Sku;
  qty: number;
  discountPercent: number;
};

function unitExVat(sku: Sku): number {
  if (sku.retail_ex_vat) {
    return Number(sku.retail_ex_vat);
  }
  if (sku.retail_inc_vat) {
    return incVatToExVat(Number(sku.retail_inc_vat));
  }
  return 0;
}

function unitIncVat(sku: Sku): number {
  if (sku.retail_inc_vat) {
    return Number(sku.retail_inc_vat);
  }
  if (sku.retail_ex_vat) {
    return exVatToIncVat(Number(sku.retail_ex_vat));
  }
  return 0;
}

function lineDiscountedEx(line: CartLine): number {
  const factor = 1 - line.discountPercent / 100;
  return roundHalfUp(unitExVat(line.sku) * factor * line.qty, 2);
}

function lineIncTotal(line: CartLine): number {
  const factor = 1 - line.discountPercent / 100;
  return roundHalfUp(unitIncVat(line.sku) * factor * line.qty, 2);
}

function cartSummary(lines: CartLine[]) {
  const subtotalIncBeforeDiscount = lines.reduce(
    (sum, line) => sum + roundHalfUp(unitIncVat(line.sku) * line.qty, 2),
    0,
  );
  const lineDiscounts = lines.reduce(
    (sum, line) =>
      sum + roundHalfUp(unitIncVat(line.sku) * line.qty * (line.discountPercent / 100), 2),
    0,
  );
  const discountedExSubtotal = lines.reduce((sum, line) => sum + lineDiscountedEx(line), 0);
  const preview = computeInvoicePreview(discountedExSubtotal);
  return {
    subtotalIncBeforeDiscount,
    lineDiscounts,
    vatIncluded: preview.vat,
    totalIncVat: preview.totalIncVat,
  };
}

function clampDiscount(value: number): number {
  if (value < 0) {
    return 0;
  }
  if (value > 100) {
    return 100;
  }
  return value;
}

export default function TillPage() {
  const router = useRouter();
  const { user } = useAuth();
  const canSell = canUseTill(user?.role);
  const [locations, setLocations] = useState<Location[]>([]);
  const [skus, setSkus] = useState<Sku[]>([]);
  const [inventory, setInventory] = useState<InventorySku[]>([]);
  const [locationId, setLocationId] = useState("");
  const [skuId, setSkuId] = useState("");
  const [qty, setQty] = useState<number | "">(1);
  const [cart, setCart] = useState<CartLine[]>([]);
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
      setLocationId((current) => current || showrooms[0]?.id || "");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load till data.");
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

  const cartQtyBySku = useMemo(() => {
    const totals = new Map<string, number>();
    for (const line of cart) {
      totals.set(line.sku.id, (totals.get(line.sku.id) ?? 0) + line.qty);
    }
    return totals;
  }, [cart]);

  const summary = cartSummary(cart);

  const addValid =
    canSell &&
    locationId &&
    skuId &&
    numericQty > 0 &&
    numericQty <= floorOnHand - (cartQtyBySku.get(skuId) ?? 0) &&
    unitExVat(selectedSku ?? ({} as Sku)) > 0;

  const saleValid =
    canSell &&
    locationId &&
    cart.length > 0 &&
    cart.every((line) => {
      const onHand =
        inventoryBySku
          .get(line.sku.id)
          ?.locations.find((loc) => loc.location_id === locationId)?.on_hand ?? 0;
      return line.qty > 0 && (cartQtyBySku.get(line.sku.id) ?? 0) <= onHand;
    });

  function handleAddToCart() {
    if (!addValid || !selectedSku) {
      return;
    }
    setCart((current) => [
      ...current,
      {
        key: `${selectedSku.id}-${Date.now()}`,
        sku: selectedSku,
        qty: numericQty,
        discountPercent: 0,
      },
    ]);
    setSkuId("");
    setQty(1);
  }

  function updateCartLine(key: string, patch: Partial<Pick<CartLine, "qty" | "discountPercent">>) {
    setCart((current) =>
      current.map((line) => {
        if (line.key !== key) {
          return line;
        }
        const nextQty = patch.qty ?? line.qty;
        const nextDiscount =
          patch.discountPercent !== undefined
            ? clampDiscount(patch.discountPercent)
            : line.discountPercent;
        return { ...line, qty: nextQty, discountPercent: nextDiscount };
      }),
    );
  }

  function removeCartLine(key: string) {
    setCart((current) => current.filter((line) => line.key !== key));
  }

  async function handleCompleteSale() {
    if (!saleValid) {
      return;
    }
    setSubmitting(true);
    setError(null);
    setLastSale(null);
    try {
      const result = await createTillSale({
        location_id: locationId,
        lines: cart.map((line) => {
          const payload: { sku_id: string; qty: number; discount_percent?: number } = {
            sku_id: line.sku.id,
            qty: line.qty,
          };
          if (line.discountPercent > 0) {
            payload.discount_percent = line.discountPercent;
          }
          return payload;
        }),
        tender,
      });
      setLastSale(result);
      setCart([]);
      setSkuId("");
      setQty(1);
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
      <div className="vellano-page-header">
        <div>
          <h1>Till</h1>
          <p>Process sales, returns, and payments.</p>
        </div>
        <ButtonSet>
          <Button
            kind="secondary"
            renderIcon={Undo}
            onClick={() => router.push("/returns")}
          >
            Process Return
          </Button>
          <Button
            kind="secondary"
            renderIcon={Currency}
            onClick={() => router.push("/laybys")}
          >
            Layby Payment
          </Button>
        </ButtonSet>
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
        <Grid>
          <Column lg={8} md={4} sm={4}>
            <Stack gap={5}>
              <Tile>
                <Stack gap={5}>
                  <h2>Add product</h2>
                  <Select
                    id="till-location"
                    labelText="Showroom"
                    value={locationId}
                    onChange={(event) => {
                      setLocationId(event.target.value);
                      setSkuId("");
                      setCart([]);
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
                    max={Math.max(floorOnHand - (cartQtyBySku.get(skuId) ?? 0), 0) || undefined}
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
                        ? `${Math.max(floorOnHand - (cartQtyBySku.get(skuId) ?? 0), 0)} available at showroom`
                        : undefined
                    }
                    disabled={!skuId}
                  />

                  <Button kind="secondary" disabled={!addValid} onClick={handleAddToCart}>
                    Add to cart
                  </Button>
                </Stack>
              </Tile>

              <Tile className="vellano-till-cart">
                {cart.length === 0 ? (
                  <p>No items in cart.</p>
                ) : (
                  <TableContainer title="Cart">
                    <Table size="sm">
                      <TableHead>
                        <TableRow>
                          <TableHeader>Item</TableHeader>
                          <TableHeader>Qty</TableHeader>
                          <TableHeader>Unit price (ZAR inc VAT)</TableHeader>
                          <TableHeader>Discount %</TableHeader>
                          <TableHeader>Total (ZAR)</TableHeader>
                          <TableHeader />
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {cart.map((line) => (
                          <TableRow key={line.key}>
                            <TableCell>
                              <strong>{line.sku.name}</strong>
                              <div className="vellano-muted-text">SKU: {line.sku.our_ref}</div>
                            </TableCell>
                            <TableCell>
                              <NumberInput
                                id={`cart-qty-${line.key}`}
                                hideLabel
                                label="Quantity"
                                size="sm"
                                min={1}
                                value={line.qty}
                                onChange={(_, { value }) => {
                                  const next =
                                    value === ""
                                      ? 1
                                      : typeof value === "number"
                                        ? value
                                        : Number(value);
                                  updateCartLine(line.key, { qty: Math.max(1, next) });
                                }}
                              />
                            </TableCell>
                            <TableCell>{formatZarAmount(formatPriceAmount(unitIncVat(line.sku)))}</TableCell>
                            <TableCell>
                              <NumberInput
                                id={`cart-discount-${line.key}`}
                                hideLabel
                                label="Discount percent"
                                size="sm"
                                min={0}
                                max={100}
                                value={line.discountPercent}
                                onChange={(_, { value }) => {
                                  const next =
                                    value === ""
                                      ? 0
                                      : typeof value === "number"
                                        ? value
                                        : Number(value);
                                  updateCartLine(line.key, { discountPercent: clampDiscount(next) });
                                }}
                              />
                            </TableCell>
                            <TableCell>
                              <strong>{formatZarAmount(formatPriceAmount(lineIncTotal(line)))}</strong>
                            </TableCell>
                            <TableCell>
                              <Button
                                kind="ghost"
                                size="sm"
                                hasIconOnly
                                renderIcon={TrashCan}
                                iconDescription="Remove line"
                                onClick={() => removeCartLine(line.key)}
                              />
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </TableContainer>
                )}
              </Tile>
            </Stack>
          </Column>

          <Column lg={4} md={4} sm={4}>
            <Tile>
              <Stack gap={5}>
                <h2>Sale summary</h2>

                <dl className="vellano-sale-summary">
                  <div className="vellano-sale-summary__row">
                    <dt>Subtotal (before discount)</dt>
                    <dd>{formatZarAmount(formatPriceAmount(summary.subtotalIncBeforeDiscount))}</dd>
                  </div>
                  <div className="vellano-sale-summary__row vellano-sale-summary__row--discount">
                    <dt>Line discounts</dt>
                    <dd>
                      {summary.lineDiscounts > 0
                        ? `- ${formatZarAmount(formatPriceAmount(summary.lineDiscounts))}`
                        : formatZarAmount(formatPriceAmount(0))}
                    </dd>
                  </div>
                  <div className="vellano-sale-summary__row">
                    <dt>VAT ({VAT_RATE_LABEL}) included</dt>
                    <dd>{formatZarAmount(formatPriceAmount(summary.vatIncluded))}</dd>
                  </div>
                  <div className="vellano-sale-summary__row vellano-sale-summary__row--total">
                    <dt>Total (ZAR)</dt>
                    <dd>{formatZarAmount(formatPriceAmount(summary.totalIncVat))}</dd>
                  </div>
                </dl>

                <div>
                  <Select
                    id="till-tender"
                    labelText="Tender"
                    value={tender}
                    onChange={(event) => setTender(event.target.value as TillTender)}
                  >
                    {TENDER_OPTIONS.map((option) => (
                      <SelectItem key={option.value} value={option.value} text={option.label} />
                    ))}
                  </Select>
                </div>

                <Button
                  kind="primary"
                  disabled={!saleValid || submitting}
                  onClick={() => void handleCompleteSale()}
                >
                  Complete Sale
                </Button>
              </Stack>
            </Tile>
          </Column>
        </Grid>
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
              <Button
                kind="secondary"
                renderIcon={Undo}
                onClick={() => router.push(`/returns?invoice=${lastSale.invoice_id}`)}
              >
                Process Return
              </Button>
            </ButtonSet>
          </Stack>
        </Tile>
      ) : null}
    </Stack>
  );
}
