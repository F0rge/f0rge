"use client";

import {
  Button,
  ButtonSet,
  Checkbox,
  ComboBox,
  InlineNotification,
  Modal,
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
  TextInput,
  Tile,
} from "@carbon/react";
import {
  Bookmark,
  Building,
  Currency,
  Image as ImageIcon,
  Money,
  Purchase,
  Scan,
  TrashCan,
  Undo,
  UserFollow,
} from "@carbon/icons-react";
import { useRouter } from "next/navigation";
import { Fragment, useCallback, useEffect, useMemo, useRef, useState } from "react";

import { CustomerPicker } from "@/components/customer-picker";
import { TillScanner } from "@/components/till-scanner";

import {
  ApiError,
  can,
  canManageCustomerCredit,
  canUseTill,
  canViewCostAudit,
  cancelPick,
  computeInvoicePreview,
  confirmPick,
  createPick,
  createTillSale,
  downloadInvoicePdf,
  getSettings,
  listPicks,
  exVatToIncVat,
  formatPriceAmount,
  formatZarAmount,
  isActiveLocation,
  listCustomers,
  listInventory,
  listLocations,
  listPriceLists,
  listSkus,
  parsePriceInput,
  roundHalfUp,
  settingsLogoUrl,
  skuPhotoUrl,
  type AppSettings,
  type CustomerCrm,
  type InventorySku,
  type Location,
  type PriceList,
  type Sku,
  type PickDocument,
  type TillSaleResult,
  type TillTender,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";
import {
  displayUnitAmount,
  pricesIncludeVat,
  quoteLineSuspectWarning,
  quoteSkuUnitExVat,
  vatBasisLabel,
} from "@/lib/quote-sku-price";
import { isCreditBlockMessage } from "@/lib/customer-crm";
import {
  clearTillCart,
  loadTillCart,
  nextTillStateAfterKitConfirm,
  openPicksHrefForKit,
  parseKitRequiresPick,
  salePickIds,
  saveTillCart,
  type TillKitBlock,
} from "@/lib/till-kit-pick";
import {
  isDesktopPointer,
  isProtectedScanField,
  isQtyOrDiscountField,
  resolveTillScan,
  tillScanErrorMessage,
} from "@/lib/barcode-scan";

const WALK_IN_CUSTOMER_NAME = "Walk-in customer";

function resolveTillLocationId(
  showrooms: Location[],
  userDefaultId: string | null | undefined,
  teamTillDefaultId: string | null | undefined,
): string {
  if (userDefaultId && showrooms.some((loc) => loc.id === userDefaultId)) {
    return userDefaultId;
  }
  if (teamTillDefaultId && showrooms.some((loc) => loc.id === teamTillDefaultId)) {
    return teamTillDefaultId;
  }
  return showrooms[0]?.id ?? "";
}

const TENDER_OPTIONS: { value: TillTender; label: string; icon: typeof Purchase }[] = [
  { value: "card", label: "Card", icon: Purchase },
  { value: "cash", label: "Cash", icon: Money },
  { value: "eft", label: "EFT", icon: Building },
  { value: "deposit", label: "Layby Deposit", icon: Bookmark },
];

type CartLine = {
  key: string;
  sku: Sku;
  qty: number;
  discountPercent: number;
};

function unitExVat(sku: Sku, customer: CustomerCrm | null, priceLists: PriceList[]): number {
  return quoteSkuUnitExVat(sku, customer, priceLists).unitExVat ?? 0;
}

function unitIncVat(sku: Sku, customer: CustomerCrm | null, priceLists: PriceList[]): number {
  const ex = unitExVat(sku, customer, priceLists);
  return ex > 0 ? exVatToIncVat(ex) : 0;
}

function lineDiscountedEx(
  line: CartLine,
  customer: CustomerCrm | null,
  priceLists: PriceList[],
): number {
  const factor = 1 - line.discountPercent / 100;
  return roundHalfUp(unitExVat(line.sku, customer, priceLists) * factor * line.qty, 2);
}

function lineIncTotal(
  line: CartLine,
  customer: CustomerCrm | null,
  priceLists: PriceList[],
): number {
  const factor = 1 - line.discountPercent / 100;
  return roundHalfUp(unitIncVat(line.sku, customer, priceLists) * factor * line.qty, 2);
}

function cartSummary(
  lines: CartLine[],
  customer: CustomerCrm | null,
  priceLists: PriceList[],
) {
  const subtotalIncBeforeDiscount = lines.reduce(
    (sum, line) => sum + roundHalfUp(unitIncVat(line.sku, customer, priceLists) * line.qty, 2),
    0,
  );
  const lineDiscounts = lines.reduce(
    (sum, line) =>
      sum +
      roundHalfUp(
        unitIncVat(line.sku, customer, priceLists) * line.qty * (line.discountPercent / 100),
        2,
      ),
    0,
  );
  const discountedExSubtotal = lines.reduce(
    (sum, line) => sum + lineDiscountedEx(line, customer, priceLists),
    0,
  );
  const subtotalExBeforeDiscount = lines.reduce(
    (sum, line) => sum + roundHalfUp(unitExVat(line.sku, customer, priceLists) * line.qty, 2),
    0,
  );
  const lineDiscountsEx = lines.reduce(
    (sum, line) =>
      sum +
      roundHalfUp(
        unitExVat(line.sku, customer, priceLists) * line.qty * (line.discountPercent / 100),
        2,
      ),
    0,
  );
  const preview = computeInvoicePreview(discountedExSubtotal);
  return {
    subtotalIncBeforeDiscount,
    subtotalExBeforeDiscount,
    lineDiscounts,
    lineDiscountsEx,
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

function skuItemToString(item: Sku | null): string {
  return item ? `${item.our_ref} — ${item.name}` : "";
}

function filterSkuItem({
  item,
  inputValue,
}: {
  item: Sku;
  inputValue: string | null;
}): boolean {
  const query = (inputValue ?? "").trim().toLowerCase();
  if (!query) {
    return true;
  }
  return (
    item.name.toLowerCase().includes(query) ||
    item.our_ref.toLowerCase().includes(query) ||
    item.our_barcode.toLowerCase().includes(query)
  );
}

function mergeCartBySku(current: CartLine[], sku: Sku, addQty: number): CartLine[] {
  const existing = current.find((line) => line.sku.id === sku.id);
  if (existing) {
    return current.map((line) =>
      line.sku.id === sku.id ? { ...line, qty: line.qty + addQty } : line,
    );
  }
  return [...current, { key: sku.id, sku, qty: addQty, discountPercent: 0 }];
}

function SkuThumb({ sku }: { sku: Sku }) {
  if (!sku.photo_storage_key) {
    return (
      <div className="firstout-till-thumb firstout-till-thumb--placeholder" aria-hidden>
        <ImageIcon size={20} />
      </div>
    );
  }
  return (
    // Cookie + 302 Tigris redirect — same as catalogue; not next/image.
    // eslint-disable-next-line @next/next/no-img-element -- session cookie, follow 302
    <img
      className="firstout-till-thumb"
      src={skuPhotoUrl(sku.id)}
      alt=""
      width={48}
      height={48}
    />
  );
}

export default function TillPage() {
  const router = useRouter();
  const { user } = useAuth();
  const canSell = canUseTill(user);
  const canDiscount = can(user, "till.discount");
  const canViewCost = canViewCostAudit(user);
  const canOverrideCredit = canManageCustomerCredit(user);
  const [locations, setLocations] = useState<Location[]>([]);
  const [companySettings, setCompanySettings] = useState<AppSettings | null>(null);
  const [skus, setSkus] = useState<Sku[]>([]);
  const [inventory, setInventory] = useState<InventorySku[]>([]);
  const [customers, setCustomers] = useState<CustomerCrm[]>([]);
  const [priceLists, setPriceLists] = useState<PriceList[]>([]);
  const [locationId, setLocationId] = useState("");
  const [skuId, setSkuId] = useState("");
  const [customerId, setCustomerId] = useState("");
  const [qty, setQty] = useState<number | "">(1);
  const [cart, setCart] = useState<CartLine[]>([]);
  const [tender, setTender] = useState<TillTender>("cash");
  const [amountTendered, setAmountTendered] = useState("");
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastSale, setLastSale] = useState<TillSaleResult | null>(null);
  const [lastBuyerName, setLastBuyerName] = useState(WALK_IN_CUSTOMER_NAME);
  const [scanValue, setScanValue] = useState("");
  const [scannerOpen, setScannerOpen] = useState(false);
  const [creditOverride, setCreditOverride] = useState(false);
  const [creditOverrideReason, setCreditOverrideReason] = useState("");
  const [creditBlock, setCreditBlock] = useState<string | null>(null);
  const [pickId, setPickId] = useState("");
  const [linkedPickIds, setLinkedPickIds] = useState<Record<string, string>>({});
  const [confirmedPicks, setConfirmedPicks] = useState<PickDocument[]>([]);
  const [kitBlocks, setKitBlocks] = useState<TillKitBlock[]>([]);
  const [pickDraft, setPickDraft] = useState<{
    kit: TillKitBlock;
    pick: PickDocument | null;
    creating: boolean;
    confirming: boolean;
    ack: boolean;
    error: string | null;
  } | null>(null);
  const scanBufferRef = useRef("");
  const [cartReady, setCartReady] = useState(false);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [locationData, skuData, inventoryData, customerData, settingsData, priceListData] =
        await Promise.all([
          listLocations(),
          listSkus(),
          listInventory(),
          listCustomers(),
          getSettings(),
          listPriceLists(),
        ]);
      const showrooms = locationData.filter(
        (loc) => isActiveLocation(loc) && loc.type === "showroom",
      );
      setLocations(showrooms);
      setCompanySettings(settingsData);
      setSkus(skuData);
      setInventory(inventoryData);
      setCustomers(customerData);
      setPriceLists(priceListData);
      setLocationId((current) => {
        if (current) {
          return current;
        }
        return resolveTillLocationId(
          showrooms,
          user?.default_location_id,
          settingsData.default_till_location_id,
        );
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load till data.");
    } finally {
      setLoading(false);
    }
  }, [user]);

  useEffect(() => {
    if (user) {
      void loadData();
    }
  }, [user, loadData]);

  const inventoryBySku = useMemo(
    () => new Map(inventory.map((entry) => [entry.sku_id, entry])),
    [inventory],
  );
  const vatRateLabel = `${companySettings?.vat_percent ?? "15"}%`;

  const selectedSku = skus.find((sku) => sku.id === skuId);
  const selectedInventory = skuId ? inventoryBySku.get(skuId) : undefined;
  const floorOnHand =
    selectedInventory?.locations.find((loc) => loc.location_id === locationId)?.on_hand ?? 0;

  const skuOptions = skus.filter((sku) => {
    if (!locationId || !sku.retail_ex_vat) {
      return false;
    }
    if (sku.is_kit) {
      return true;
    }
    const row = inventoryBySku.get(sku.id);
    if (!row) {
      return false;
    }
    const atLocation = row.locations.find((loc) => loc.location_id === locationId);
    return (atLocation?.on_hand ?? 0) > 0;
  });

  const selectedSkuOption = skuOptions.find((sku) => sku.id === skuId) ?? null;
  const selectedCustomer = customers.find((customer) => customer.id === customerId) ?? null;

  useEffect(() => {
    setCreditOverride(false);
    setCreditOverrideReason("");
    setCreditBlock(null);
  }, [customerId]);

  const numericQty = typeof qty === "number" ? qty : 0;

  const cartQtyBySku = useMemo(() => {
    const totals = new Map<string, number>();
    for (const line of cart) {
      totals.set(line.sku.id, (totals.get(line.sku.id) ?? 0) + line.qty);
    }
    return totals;
  }, [cart]);

  const cartKits = useMemo(() => cart.filter((line) => line.sku.is_kit), [cart]);
  const cartKitKey = cartKits
    .map((line) => line.sku.id)
    .sort()
    .join(",");

  useEffect(() => {
    if (!cartKitKey) {
      setConfirmedPicks([]);
      return;
    }
    const kitIds = new Set(cartKitKey.split(","));
    let cancelled = false;
    listPicks()
      .then((picks) => {
        if (!cancelled) {
          setConfirmedPicks(
            picks.filter((entry) => entry.status === "confirmed" && kitIds.has(entry.sku_id)),
          );
        }
      })
      .catch(() => {
        if (!cancelled) {
          setConfirmedPicks([]);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [cartKitKey]);

  useEffect(() => {
    if (loading || cartReady) {
      return;
    }
    const snapshot = loadTillCart();
    if (!snapshot) {
      setCartReady(true);
      return;
    }
    if (skus.length === 0) {
      return;
    }
    const byId = new Map(skus.map((sku) => [sku.id, sku]));
    const lines: CartLine[] = [];
    for (const line of snapshot.lines) {
      const sku = byId.get(line.skuId);
      if (!sku) {
        continue;
      }
      lines.push({
        key: sku.id,
        sku,
        qty: line.qty,
        discountPercent: line.discountPercent,
      });
    }
    if (lines.length > 0) {
      setCart(lines);
    }
    if (snapshot.locationId) {
      setLocationId(snapshot.locationId);
    }
    if (snapshot.customerId) {
      setCustomerId(snapshot.customerId);
    }
    if (snapshot.pickId) {
      setPickId(snapshot.pickId);
    }
    if (Object.keys(snapshot.linkedPickIds).length > 0) {
      setLinkedPickIds(snapshot.linkedPickIds);
    }
    setCartReady(true);
  }, [cartReady, loading, skus]);

  useEffect(() => {
    if (!cartReady) {
      return;
    }
    saveTillCart({
      locationId,
      customerId,
      pickId,
      linkedPickIds,
      lines: cart.map((line) => ({
        skuId: line.sku.id,
        qty: line.qty,
        discountPercent: line.discountPercent,
      })),
    });
  }, [cart, cartReady, customerId, linkedPickIds, locationId, pickId]);

  const summary = cartSummary(cart, selectedCustomer, priceLists);
  const showInclusive = pricesIncludeVat(selectedCustomer);
  const totalIncLabel = formatPriceAmount(summary.totalIncVat);

  useEffect(() => {
    setAmountTendered(totalIncLabel);
  }, [totalIncLabel]);

  const tenderedAmount = parsePriceInput(amountTendered) ?? summary.totalIncVat;
  const changeAmount = Math.max(0, tenderedAmount - summary.totalIncVat);
  const showChange = tender === "cash" || tender === "eft";

  const addValid =
    canSell &&
    locationId &&
    skuId &&
    numericQty > 0 &&
    (selectedSku?.is_kit ||
      numericQty <= floorOnHand - (cartQtyBySku.get(skuId) ?? 0)) &&
    unitExVat(selectedSku ?? ({} as Sku), selectedCustomer, priceLists) > 0;

  const floorOnHandFor = useCallback(
    (id: string) =>
      inventoryBySku.get(id)?.locations.find((loc) => loc.location_id === locationId)?.on_hand ??
      0,
    [inventoryBySku, locationId],
  );

  const focusScanField = useCallback(() => {
    if (!isDesktopPointer()) {
      return;
    }
    document.getElementById("till-scan")?.focus();
  }, []);

  useEffect(() => {
    if (!loading) {
      focusScanField();
    }
  }, [loading, focusScanField]);

  const applyScan = useCallback(
    (code: string, allowOurRef: boolean, addQty = 1): boolean => {
      if (!canSell || !locationId) {
        return false;
      }
      const trimmed = code.trim();
      if (!trimmed) {
        return false;
      }
      const result = resolveTillScan({
        code: trimmed,
        skus,
        allowOurRef,
        addQty,
        floorOnHand: floorOnHandFor,
        cartQty: (id) => cartQtyBySku.get(id) ?? 0,
      });
      if (!result.ok) {
        setError(tillScanErrorMessage(result.error));
        return false;
      }
      setError(null);
      setCart((current) => mergeCartBySku(current, result.sku, result.qty));
      setScanValue("");
      focusScanField();
      return true;
    },
    [canSell, cartQtyBySku, floorOnHandFor, focusScanField, locationId, skus],
  );

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      const target = event.target instanceof Element ? event.target : document.activeElement;
      if (isQtyOrDiscountField(target)) {
        return;
      }
      if (isProtectedScanField(target)) {
        return;
      }
      if (event.ctrlKey || event.metaKey || event.altKey) {
        return;
      }
      if (event.key === "Enter") {
        const buffered = scanBufferRef.current;
        scanBufferRef.current = "";
        if (buffered.trim()) {
          event.preventDefault();
          applyScan(buffered, true);
        }
        return;
      }
      if (event.key.length === 1) {
        scanBufferRef.current += event.key;
      } else if (event.key === "Backspace") {
        scanBufferRef.current = scanBufferRef.current.slice(0, -1);
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [applyScan]);

  const saleValid =
    canSell &&
    locationId &&
    cart.length > 0 &&
    cart.every((line) => {
      if (line.sku.is_kit) {
        return line.qty > 0;
      }
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
    if (selectedSku.is_kit) {
      setError(null);
      setCart((current) => mergeCartBySku(current, selectedSku, numericQty));
      setSkuId("");
      setQty(1);
      return;
    }
    if (applyScan(selectedSku.our_barcode, false, numericQty)) {
      setSkuId("");
      setQty(1);
    }
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
    if (creditOverride && canOverrideCredit && !creditOverrideReason.trim()) {
      setError("Override reason is required.");
      return;
    }
    setSubmitting(true);
    setError(null);
    setCreditBlock(null);
    setKitBlocks([]);
    setLastSale(null);
    try {
      const pickIds = salePickIds(linkedPickIds, pickId);
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
        ...(customerId ? { customer_id: customerId } : {}),
        ...(pickId ? { pick_id: pickId } : {}),
        ...(pickIds.length > 0 ? { pick_ids: pickIds } : {}),
        ...(canOverrideCredit && creditOverride
          ? {
              credit_override: true,
              credit_override_reason: creditOverrideReason.trim(),
            }
          : {}),
      });
      setLastBuyerName(selectedCustomer?.name ?? WALK_IN_CUSTOMER_NAME);
      setLastSale(result);
      setCart([]);
      setSkuId("");
      setCustomerId("");
      setPickId("");
      setLinkedPickIds({});
      setKitBlocks([]);
      clearTillCart();
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
      if (err instanceof ApiError && err.status === 409 && isCreditBlockMessage(err.message)) {
        setCreditBlock(err.message);
      }
      if (err instanceof ApiError && err.status === 409) {
        const parsed = parseKitRequiresPick(err.detail);
        if (parsed) {
          setKitBlocks(parsed.kits);
          setError(null);
        }
      }
    } finally {
      setSubmitting(false);
    }
  }

  function rememberConfirmedPick(kit: TillKitBlock, confirmed: PickDocument) {
    const next = nextTillStateAfterKitConfirm(
      { cart, pickId, linkedPickIds, blocks: kitBlocks },
      { id: confirmed.id, skuId: kit.sku_id },
    );
    setPickId(next.pickId);
    setLinkedPickIds(next.linkedPickIds);
    setKitBlocks(next.blocks);
    setConfirmedPicks((current) => [
      confirmed,
      ...current.filter((entry) => entry.id !== confirmed.id),
    ]);
    setPickDraft(null);
    setError(null);
  }

  async function startKitPick(kit: TillKitBlock) {
    setPickDraft({
      kit,
      pick: null,
      creating: true,
      confirming: false,
      ack: false,
      error: null,
    });
    try {
      const created = await createPick({
        sku_id: kit.sku_id,
        qty: kit.qty,
        ...(customerId ? { customer_id: customerId } : {}),
      });
      setPickDraft((current) =>
        current && current.kit.sku_id === kit.sku_id
          ? { ...current, pick: created, creating: false }
          : current,
      );
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "Could not create the pick.";
      setPickDraft((current) =>
        current && current.kit.sku_id === kit.sku_id
          ? { ...current, creating: false, error: message }
          : current,
      );
    }
  }

  async function confirmKitPick() {
    if (!pickDraft?.pick || pickDraft.confirming) {
      return;
    }
    const requireAck = pickDraft.pick.needs_confirm;
    if (requireAck && !pickDraft.ack) {
      setPickDraft({ ...pickDraft, error: "Acknowledge the split before confirming." });
      return;
    }
    if (pickDraft.pick.qty_short) {
      setPickDraft({
        ...pickDraft,
        error: "There are not enough parts in stock to confirm this pick.",
      });
      return;
    }
    setPickDraft({ ...pickDraft, confirming: true, error: null });
    try {
      const confirmed = await confirmPick(pickDraft.pick.id, requireAck ? true : undefined);
      rememberConfirmedPick(pickDraft.kit, confirmed);
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "Could not confirm the pick.";
      setPickDraft((current) => (current ? { ...current, confirming: false, error: message } : current));
    }
  }

  async function dismissPickDraft() {
    const draft = pickDraft;
    setPickDraft(null);
    if (draft?.pick && draft.pick.status === "draft") {
      try {
        await cancelPick(draft.pick.id);
      } catch {
        // Leave the draft on the picks list if cancel fails.
      }
    }
  }

  function openPicksForKit(kit: TillKitBlock) {
    saveTillCart({
      locationId,
      customerId,
      pickId,
      linkedPickIds,
      lines: cart.map((line) => ({
        skuId: line.sku.id,
        qty: line.qty,
        discountPercent: line.discountPercent,
      })),
    });
    router.push(openPicksHrefForKit(kit));
  }

  if (!canSell) {
    return (
      <Stack gap={5}>
        <h1 className="cds--type-productive-heading-04">Till</h1>
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
    <Stack gap={6} className="firstout-till">
      <div className="firstout-page-header">
        <div>
          <h1 className="cds--type-productive-heading-04">Till</h1>
          <p className="cds--type-body-01">Process sales, returns, and payments.</p>
        </div>
        <div className="firstout-catalogue-actions">
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
            onClick={() => router.push("/laybys?new=1")}
          >
            Layby Payment
          </Button>
        </div>
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

      {kitBlocks.map((kit) => (
        <Stack key={`${kit.sku_id}-${kit.qty}`} gap={3}>
          <InlineNotification
            kind="warning"
            title={`${kit.sku_name} (${kit.sku_code})`}
            subtitle={kit.message}
            hideCloseButton
            lowContrast
          />
          <div className="firstout-catalogue-actions">
            <Button kind="primary" onClick={() => void startKitPick(kit)}>
              Create pick for this kit
            </Button>
            <Button kind="ghost" onClick={() => openPicksForKit(kit)}>
              Open picks
            </Button>
          </div>
        </Stack>
      ))}

      {loading ? (
        <p>Loading…</p>
      ) : (
        <div className="firstout-till-layout">
          <div className="firstout-till-layout__main">
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

                  <div className="firstout-till-scan-row">
                    <TextInput
                      id="till-scan"
                      labelText="Scan barcode"
                      placeholder="Scan or type our barcode"
                      value={scanValue}
                      onChange={(event) => setScanValue(event.target.value)}
                      onKeyDown={(event) => {
                        if (event.key === "Enter") {
                          event.preventDefault();
                          applyScan(scanValue, true);
                        }
                      }}
                      disabled={!locationId}
                    />
                    <Button
                      kind="secondary"
                      renderIcon={Scan}
                      disabled={!locationId}
                      onClick={() => setScannerOpen(true)}
                    >
                      Scan
                    </Button>
                  </div>

                  <div className="firstout-till-picker-row">
                    <ComboBox
                      id="till-sku"
                      titleText="SKU"
                      placeholder="Search by SKU, barcode, or name..."
                      items={skuOptions}
                      itemToString={skuItemToString}
                      selectedItem={selectedSkuOption}
                      shouldFilterItem={filterSkuItem}
                      onChange={({ selectedItem }) => setSkuId(selectedItem?.id ?? "")}
                      disabled={!locationId}
                    />
                    <Button kind="secondary" onClick={() => router.push("/catalogue")}>
                      Browse Catalogue
                    </Button>
                  </div>

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

                  <Button data-tour="till-add" kind="secondary" disabled={!addValid} onClick={handleAddToCart}>
                    Add to cart
                  </Button>
                </Stack>
              </Tile>

              <Tile className="firstout-till-cart">
                {cart.length === 0 ? (
                  <p>No items in cart.</p>
                ) : (
                  <TableContainer title="Cart">
                    <Table size="sm">
                      <TableHead>
                        <TableRow>
                          <TableHeader className="firstout-till-thumb-cell">
                            <span className="cds--visually-hidden">Photo</span>
                          </TableHeader>
                          <TableHeader>Item</TableHeader>
                          <TableHeader>Qty</TableHeader>
                          <TableHeader>
                            Unit price ({vatBasisLabel(showInclusive)})
                          </TableHeader>
                          {canDiscount ? <TableHeader>Discount %</TableHeader> : null}
                          <TableHeader>Total (ZAR)</TableHeader>
                          <TableHeader />
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {cart.map((line) => {
                          const priced = quoteSkuUnitExVat(line.sku, selectedCustomer, priceLists);
                          const suspect = quoteLineSuspectWarning(
                            priced.unitExVat === null ? "" : formatPriceAmount(priced.unitExVat),
                            line.sku,
                            priced,
                            canViewCost,
                          );
                          const columnCount = canDiscount ? 7 : 6;
                          return (
                          <Fragment key={line.key}>
                          <TableRow>
                            <TableCell className="firstout-till-thumb-cell">
                              <SkuThumb sku={line.sku} />
                            </TableCell>
                            <TableCell>
                              <strong>{line.sku.name}</strong>
                              <div className="firstout-muted-text">SKU: {line.sku.our_ref}</div>
                              {priced.warning ? (
                                <div className="firstout-muted-text">{priced.warning}</div>
                              ) : null}
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
                            <TableCell>
                              {formatZarAmount(
                                formatPriceAmount(
                                  displayUnitAmount(
                                    unitExVat(line.sku, selectedCustomer, priceLists),
                                    showInclusive,
                                  ),
                                ),
                              )}
                            </TableCell>
                            {canDiscount ? (
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
                            ) : null}
                            <TableCell>
                              <strong>
                                {formatZarAmount(
                                  formatPriceAmount(lineIncTotal(line, selectedCustomer, priceLists)),
                                )}
                              </strong>
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
                          {suspect ? (
                            <TableRow>
                              <TableCell colSpan={columnCount}>
                                <InlineNotification
                                  className="firstout-till-price-warning"
                                  kind="warning"
                                  lowContrast
                                  hideCloseButton
                                  title="Check this price"
                                  subtitle={suspect}
                                />
                              </TableCell>
                            </TableRow>
                          ) : null}
                          </Fragment>
                          );
                        })}
                      </TableBody>
                    </Table>
                  </TableContainer>
                )}
              </Tile>
            </Stack>
          </div>

          <div className="firstout-till-layout__summary">
            <Tile>
              <Stack gap={5}>
                <h2>Sale summary</h2>

                <dl className="firstout-sale-summary">
                  <div className="firstout-sale-summary__row">
                    <dt>
                      {showInclusive ? "Subtotal (before discount, incl. VAT)" : "Subtotal excl. VAT"}
                    </dt>
                    <dd>
                      {formatZarAmount(
                        formatPriceAmount(
                          showInclusive
                            ? summary.subtotalIncBeforeDiscount
                            : summary.subtotalExBeforeDiscount,
                        ),
                      )}
                    </dd>
                  </div>
                  <div className="firstout-sale-summary__row firstout-sale-summary__row--discount">
                    <dt>{showInclusive ? "Line discounts" : "Line discounts excl. VAT"}</dt>
                    <dd>
                      {(showInclusive ? summary.lineDiscounts : summary.lineDiscountsEx) > 0
                        ? `- ${formatZarAmount(
                            formatPriceAmount(
                              showInclusive ? summary.lineDiscounts : summary.lineDiscountsEx,
                            ),
                          )}`
                        : formatZarAmount(formatPriceAmount(0))}
                    </dd>
                  </div>
                  <div className="firstout-sale-summary__row">
                    <dt>{showInclusive ? `VAT (${vatRateLabel}) included` : `VAT (${vatRateLabel})`}</dt>
                    <dd>{formatZarAmount(formatPriceAmount(summary.vatIncluded))}</dd>
                  </div>
                  <div className="firstout-sale-summary__row firstout-sale-summary__row--total">
                    <dt>{showInclusive ? "Total (incl. VAT)" : "Total incl. VAT"}</dt>
                    <dd>{formatZarAmount(formatPriceAmount(summary.totalIncVat))}</dd>
                  </div>
                </dl>

                <div className="firstout-till-picker-row">
                  <CustomerPicker
                    id="till-customer"
                    titleText="Customer (optional)"
                    customers={customers}
                    selectedId={customerId}
                    onChange={setCustomerId}
                  />
                  <Button
                    kind="ghost"
                    hasIconOnly
                    renderIcon={UserFollow}
                    iconDescription="Add customer"
                    onClick={() => router.push("/customers")}
                  />
                </div>

                {selectedCustomer?.on_hold ? (
                  <InlineNotification
                    kind="warning"
                    title="Customer is on hold"
                    subtitle={
                      selectedCustomer.on_hold_reason ||
                      "This customer cannot be sold to until the hold is lifted."
                    }
                    hideCloseButton
                    lowContrast
                  />
                ) : null}

                {confirmedPicks.length > 0 ? (
                  <Select
                    id="till-pick"
                    labelText="Confirmed pick"
                    value={pickId}
                    onChange={(event) => setPickId(event.target.value)}
                  >
                    <SelectItem value="" text="Select pick" />
                    {confirmedPicks.map((entry) => (
                      <SelectItem
                        key={entry.id}
                        value={entry.id}
                        text={`${entry.pick_number || entry.id} · ${entry.sku_our_ref || entry.sku_id} × ${entry.qty}`}
                      />
                    ))}
                  </Select>
                ) : null}

                {canOverrideCredit && (selectedCustomer?.on_hold || creditBlock) ? (
                  <>
                    <Checkbox
                      id="till-credit-override"
                      labelText="Override credit hold / limit"
                      checked={creditOverride}
                      onChange={() => setCreditOverride((current) => !current)}
                    />
                    {creditOverride ? (
                      <TextInput
                        id="till-credit-override-reason"
                        labelText="Override reason"
                        value={creditOverrideReason}
                        onChange={(event) => setCreditOverrideReason(event.target.value)}
                      />
                    ) : null}
                  </>
                ) : null}

                <div>
                  <h3>Tender</h3>
                  <div className="firstout-tender-grid">
                    {TENDER_OPTIONS.map((option) => {
                      const Icon = option.icon;
                      const isSelected = tender === option.value;
                      return (
                        <button
                          key={option.value}
                          type="button"
                          className={
                            isSelected
                              ? "firstout-tender-tile firstout-tender-tile--selected"
                              : "firstout-tender-tile"
                          }
                          aria-pressed={isSelected}
                          onClick={() => setTender(option.value)}
                        >
                          <Icon size={20} aria-hidden />
                          <span>{option.label}</span>
                        </button>
                      );
                    })}
                  </div>
                </div>

                <TextInput
                  id="till-amount-tendered"
                  labelText="Amount Tendered"
                  value={amountTendered}
                  onChange={(event) => setAmountTendered(event.target.value)}
                />

                {showChange ? (
                  <p className="firstout-muted-text">
                    Change: {formatZarAmount(formatPriceAmount(changeAmount))}
                  </p>
                ) : null}

                <Button
                  kind="primary"
                  disabled={
                    !saleValid ||
                    submitting ||
                    (creditOverride && canOverrideCredit && !creditOverrideReason.trim())
                  }
                  onClick={() => void handleCompleteSale()}
                >
                  Complete Sale
                </Button>
              </Stack>
            </Tile>
          </div>
        </div>
      )}

      {scannerOpen ? (
        <TillScanner
          onClose={() => setScannerOpen(false)}
          onDetect={(code) => applyScan(code, false)}
          onTypeIn={(code) => applyScan(code, true)}
        />
      ) : null}

      {lastSale ? (
        <Tile className="firstout-tax-invoice">
          <Stack gap={5}>
            <div className="firstout-tax-invoice__header">
              <h2>Tax invoice {lastSale.invoice_number}</h2>
              <p>
                Payment {lastSale.payment_number} — {lastSale.tender}
              </p>
            </div>

            <div className="firstout-tax-invoice__parties">
              <div>
                <strong>Seller</strong>
                {companySettings?.has_logo ? (
                  // eslint-disable-next-line @next/next/no-img-element -- session cookie, follow 302
                  <img
                    className="firstout-company-logo"
                    src={settingsLogoUrl()}
                    alt=""
                  />
                ) : null}
                <p>{companySettings?.legal_name ?? "—"}</p>
                <p>{companySettings?.address ?? "—"}</p>
                <p>VAT no. {companySettings?.vat_number ?? "—"}</p>
              </div>
              <div>
                <strong>Buyer</strong>
                <p>{lastBuyerName}</p>
              </div>
            </div>

            <p className="cds--type-helper-text-01">
              {lastSale.prices_include_vat
                ? "Unit prices incl. VAT"
                : "Unit prices excl. VAT. VAT is added to the total."}
            </p>
            <TableContainer>
              <Table size="sm">
                <TableHead>
                  <TableRow>
                    <TableHeader>Description</TableHeader>
                    <TableHeader>Qty</TableHeader>
                    <TableHeader>
                      {lastSale.prices_include_vat ? "Unit incl. VAT" : "Unit excl. VAT"}
                    </TableHeader>
                    <TableHeader>Ex VAT</TableHeader>
                    <TableHeader>VAT</TableHeader>
                    <TableHeader>Inc VAT</TableHeader>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {lastSale.lines.map((line) => (
                    <TableRow key={line.id}>
                      <TableCell>
                        {line.description}
                        {line.price_warning ? (
                          <div className="firstout-muted-text">{line.price_warning}</div>
                        ) : null}
                        {line.suspect_price_warning ? (
                          <div className="firstout-price-warning">{line.suspect_price_warning}</div>
                        ) : null}
                      </TableCell>
                      <TableCell>{line.qty}</TableCell>
                      <TableCell>
                        {formatZarAmount(
                          lastSale.prices_include_vat
                            ? formatPriceAmount(exVatToIncVat(Number(line.unit_ex_vat)))
                            : line.unit_ex_vat,
                        )}
                      </TableCell>
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
              <p>VAT ({vatRateLabel}): {formatZarAmount(lastSale.vat_amount)}</p>
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

      <Modal
        open={pickDraft !== null}
        modalHeading={
          pickDraft
            ? `Create pick for ${pickDraft.kit.sku_name}`
            : "Create pick for this kit"
        }
        primaryButtonText={
          pickDraft?.confirming ? "Confirming…" : pickDraft?.creating ? "Creating…" : "Confirm pick"
        }
        secondaryButtonText="Cancel"
        primaryButtonDisabled={
          !pickDraft?.pick ||
          pickDraft.creating ||
          pickDraft.confirming ||
          pickDraft.pick.qty_short ||
          (pickDraft.pick.needs_confirm && !pickDraft.ack)
        }
        onRequestClose={() => void dismissPickDraft()}
        onRequestSubmit={() => void confirmKitPick()}
      >
        {pickDraft ? (
          <Stack gap={4}>
            <p className="cds--type-body-01">
              {pickDraft.kit.sku_name} ({pickDraft.kit.sku_code}) × {pickDraft.kit.qty}. A pick
              tells the warehouse which storeroom each part comes from. The cart stays on the till.
            </p>
            {pickDraft.creating ? <p className="cds--type-body-01">Creating the pick…</p> : null}
            {pickDraft.pick
              ? pickDraft.pick.lines.map((line) => (
                  <p key={line.sku_id} className="cds--type-body-01">
                    {line.sku_name || line.sku_our_ref} × {line.qty_needed}
                  </p>
                ))
              : null}
            {pickDraft.pick?.needs_confirm ? (
              <>
                <InlineNotification
                  kind="warning"
                  title="Split pick"
                  subtitle="These parts are in more than one place. Tick the box so the warehouse can take them from those locations."
                  hideCloseButton
                  lowContrast
                />
                <Checkbox
                  id="till-pick-ack-split"
                  labelText="I acknowledge this split pick"
                  checked={pickDraft.ack}
                  onChange={() =>
                    setPickDraft((current) => (current ? { ...current, ack: !current.ack } : current))
                  }
                />
              </>
            ) : null}
            {pickDraft.pick?.qty_short ? (
              <InlineNotification
                kind="error"
                title="Not enough parts"
                subtitle="This pick cannot be confirmed until the missing parts are in stock."
                hideCloseButton
                lowContrast
              />
            ) : null}
            {pickDraft.error ? (
              <InlineNotification
                kind="error"
                title="Pick"
                subtitle={pickDraft.error}
                hideCloseButton
                lowContrast
              />
            ) : null}
          </Stack>
        ) : null}
      </Modal>
    </Stack>
  );
}
