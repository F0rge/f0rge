"use client";

import { StaffImage } from "@/components/staff-image";

import {
  Button,
  ButtonSet,
  Checkbox,
  ClickableTile,
  ComboBox,
  InlineNotification,
  Modal,
  NumberInput,
  Pagination,
  RadioButton,
  RadioButtonGroup,
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
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  useSyncExternalStore,
} from "react";

import { CustomerPicker } from "@/components/customer-picker";
import { TillScanner } from "@/components/till-scanner";
import {
  getMobileScanServerSnapshot,
  getMobileScanSnapshot,
  subscribeMobileScan,
} from "@/lib/mobile-scan";
import { formatQuantity } from "@/lib/quantity";
import styles from "./page.module.css";
import { TillLoading } from "./loading-layout";

import {
  ApiError,
  can,
  canManageCustomerCredit,
  canUseTill,
  canViewCostAudit,
  cancelPick,
  confirmPick,
  createPick,
  createTillSale,
  downloadInvoicePdf,
  getSettings,
  getSku,
  getCustomer,
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
  previewTillPrices,
  settingsLogoUrl,
  skuPhotoUrl,
  type AppSettings,
  type CustomerCrm,
  type InventorySku,
  type Location,
  type PriceList,
  type Sku,
  type PickDocument,
  type TillPricePreview,
  type TillPriceRequest,
  type TillSaleResult,
  type TillTender,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";
import {
  canResumeArchivedTillPick,
  isPendingTillPick,
  restoreTillCartSkus,
} from "@/lib/till-archive";
import {
  classificationOf,
  displayUnitAmount,
  isCin7GeneratedPriceList,
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
  requiresTillFloorStock,
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
  if (
    teamTillDefaultId &&
    showrooms.some((loc) => loc.id === teamTillDefaultId)
  ) {
    return teamTillDefaultId;
  }
  return showrooms[0]?.id ?? "";
}

const TENDER_OPTIONS: {
  value: TillTender;
  label: string;
  icon: typeof Purchase;
}[] = [
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

function unitExVat(
  sku: Sku,
  customer: CustomerCrm | null,
  priceLists: PriceList[],
): number {
  return quoteSkuUnitExVat(sku, customer, priceLists).unitExVat ?? 0;
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

function mergeCartBySku(
  current: CartLine[],
  sku: Sku,
  addQty: number,
): CartLine[] {
  if (sku.is_archived) return current;
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
      <div
        className="firstout-till-thumb firstout-till-thumb--placeholder"
        aria-hidden
      >
        <ImageIcon size={20} />
      </div>
    );
  }
  return (
    <StaffImage
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
  const mobileScan = useSyncExternalStore(
    subscribeMobileScan,
    getMobileScanSnapshot,
    getMobileScanServerSnapshot,
  );
  const [productQuery, setProductQuery] = useState("");
  const [productPage, setProductPage] = useState(1);
  const [productPageSize, setProductPageSize] = useState(12);
  const { user } = useAuth();
  const canSell = canUseTill(user);
  const canDiscount = can(user, "till.discount");
  const canViewCost = canViewCostAudit(user);
  const canOverrideCredit = canManageCustomerCredit(user);
  const [locations, setLocations] = useState<Location[]>([]);
  const [companySettings, setCompanySettings] = useState<AppSettings | null>(
    null,
  );
  const [skus, setSkus] = useState<Sku[]>([]);
  const [inventory, setInventory] = useState<InventorySku[]>([]);
  const [customers, setCustomers] = useState<CustomerCrm[]>([]);
  const [priceLists, setPriceLists] = useState<PriceList[]>([]);
  const [locationId, setLocationId] = useState("");
  const [skuId, setSkuId] = useState("");
  const [customerId, setCustomerId] = useState("");
  const [qty, setQty] = useState<number | "">(1);
  const [cart, setCart] = useState<CartLine[]>([]);
  const [pricing, setPricing] = useState<{
    request: TillPriceRequest;
    attempt: number;
    preview?: TillPricePreview;
    error?: string;
  } | null>(null);
  const [pricingAttempt, setPricingAttempt] = useState(0);
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
  const [linkedPickIds, setLinkedPickIds] = useState<Record<string, string>>(
    {},
  );
  const [confirmedPicks, setConfirmedPicks] = useState<PickDocument[]>([]);
  const [tillPicks, setTillPicks] = useState<PickDocument[]>([]);
  const [resumePickId, setResumePickId] = useState("");
  const [resumingPick, setResumingPick] = useState(false);
  const [commitmentCustomer, setCommitmentCustomer] =
    useState<CustomerCrm | null>(null);
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
      const [
        locationData,
        skuData,
        inventoryData,
        customerData,
        settingsData,
        priceListData,
        pickData,
      ] = await Promise.all([
        listLocations(),
        listSkus(),
        listInventory(),
        listCustomers(),
        getSettings(),
        listPriceLists(),
        listPicks("till"),
      ]);
      const showrooms = locationData.filter(
        (loc) => isActiveLocation(loc) && loc.type === "showroom",
      );
      setLocations(showrooms);
      setCompanySettings(settingsData);
      setSkus(skuData.filter((sku) => !sku.is_archived));
      setTillPicks(pickData);
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
      setError(
        err instanceof Error ? err.message : "Failed to load till data.",
      );
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
    selectedInventory?.locations.find((loc) => loc.location_id === locationId)
      ?.on_hand ?? 0;
  const selectedNeedsFloorStock = selectedSku && requiresTillFloorStock(selectedSku);

  const selectedCustomer =
    customers.find((customer) => customer.id === customerId) ??
    (commitmentCustomer?.id === customerId ? commitmentCustomer : null);

  const skuOptions = skus.filter((sku) => {
    if (sku.is_archived || !sku.is_sellable || !locationId) return false;
    if (sku.till_no_stock_required && !sku.is_kit) {
      return unitExVat(sku, selectedCustomer, priceLists) > 0;
    }
    if (!sku.retail_ex_vat) return false;
    if (sku.is_kit) return true;
    const row = inventoryBySku.get(sku.id);
    if (!row) {
      return false;
    }
    const atLocation = row.locations.find(
      (loc) => loc.location_id === locationId,
    );
    return (atLocation?.on_hand ?? 0) > 0;
  });

  const browserProducts = skuOptions.filter(
    (sku) =>
      filterSkuItem({ item: sku, inputValue: productQuery }) ||
      skuItemToString(sku).toLowerCase().includes(productQuery.toLowerCase()),
  );
  const browserPage = Math.min(
    productPage,
    Math.max(1, Math.ceil(browserProducts.length / productPageSize)),
  );
  const visibleProducts = browserProducts.slice(
    (browserPage - 1) * productPageSize,
    browserPage * productPageSize,
  );

  const selectedSkuOption = skuOptions.find((sku) => sku.id === skuId) ?? null;
  const pendingTillPicks = tillPicks.filter(isPendingTillPick);

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
  const selectedRemaining = Math.max(floorOnHand - (cartQtyBySku.get(skuId) ?? 0), 0);

  const cartKits = useMemo(
    () => cart.filter((line) => line.sku.is_kit),
    [cart],
  );
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
    listPicks("till")
      .then((picks) => {
        if (!cancelled) {
          setTillPicks(picks);
          setConfirmedPicks(
            picks.filter(
              (entry) => isPendingTillPick(entry) && kitIds.has(entry.sku_id),
            ),
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
    if (loading || cartReady) return;
    const snapshot = loadTillCart();
    if (!snapshot) {
      setCartReady(true);
      return;
    }
    let cancelled = false;
    void (async () => {
      const byId = await restoreTillCartSkus(snapshot, skus, tillPicks, getSku);
      const lines = snapshot.lines.flatMap((line) => {
        const sku = byId.get(line.skuId);
        return sku
          ? [
              {
                key: sku.id,
                sku,
                qty: line.qty,
                discountPercent: line.discountPercent,
              },
            ]
          : [];
      });
      const retainedCustomer =
        snapshot.customerId &&
        !customers.some((item) => item.id === snapshot.customerId) &&
        lines.some((line) => line.sku.is_archived)
          ? await getCustomer(snapshot.customerId)
          : null;
      if (cancelled) return;
      setCart(lines);
      setCommitmentCustomer(retainedCustomer);
      if (snapshot.locationId) setLocationId(snapshot.locationId);
      if (snapshot.customerId) setCustomerId(snapshot.customerId);
      setPickId(snapshot.pickId);
      setLinkedPickIds(snapshot.linkedPickIds);
      if (lines.length !== snapshot.lines.length)
        setError(
          "Some saved items are no longer available for sale and have not been restored. Archived kits require their original, unconsumed till pick at its exact quantity.",
        );
      setCartReady(true);
    })().catch(() => {
      if (!cancelled)
        setError(
          "The saved cart could not be restored. Reload the till to retry; the saved cart has not been changed.",
        );
    });
    return () => {
      cancelled = true;
    };
  }, [cartReady, customers, loading, skus, tillPicks]);

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

  const priceRequest = useMemo<TillPriceRequest>(() => ({
    ...(customerId ? { customer_id: customerId } : {}),
    lines: cart.map((line) => ({
      sku_id: line.sku.id,
      qty: line.qty,
      ...(line.discountPercent > 0 ? { discount_percent: line.discountPercent } : {}),
    })),
  }), [cart, customerId]);
  const activePricing = pricing?.request === priceRequest && pricing.attempt === pricingAttempt
    ? pricing
    : null;
  const pricePreview = activePricing?.preview;
  const pricingError = activePricing?.error;
  const refreshPrices = () => setPricingAttempt((attempt) => attempt + 1);

  useEffect(() => {
    if (!canSell || !cartReady || priceRequest.lines.length === 0) return;
    const controller = new AbortController();
    void previewTillPrices(priceRequest, controller.signal).then((preview) => {
      if (!controller.signal.aborted) {
        setPricing({ request: priceRequest, attempt: pricingAttempt, preview });
      }
    }).catch((err: unknown) => {
      if (!controller.signal.aborted) {
        setPricing({
          request: priceRequest,
          attempt: pricingAttempt,
          error: err instanceof Error ? err.message : "Could not check the sale prices.",
        });
      }
    });
    return () => controller.abort();
  }, [canSell, cartReady, priceRequest, pricingAttempt]);

  const showInclusive = pricePreview?.prices_include_vat ?? pricesIncludeVat(selectedCustomer);
  const classification = pricePreview?.classification ?? classificationOf(selectedCustomer);
  const assignedPriceList = priceLists.find((list) => list.id === selectedCustomer?.price_list_id);
  const priceListName = pricePreview
    ? pricePreview.price_list_name
    : assignedPriceList && !isCin7GeneratedPriceList(assignedPriceList.name) ? assignedPriceList.name : null;
  const totalInc = Number(pricePreview?.total_inc_vat ?? 0);
  const totalIncLabel = pricePreview || !cart.length ? formatPriceAmount(totalInc) : "";
  const money = (amount: string | number | undefined) =>
    amount === undefined ? (cart.length ? "—" : formatZarAmount("0.00")) : formatZarAmount(formatPriceAmount(Number(amount)));
  const beforeDiscount = pricePreview
    ? Number(showInclusive ? pricePreview.before_discount_inc_vat : pricePreview.before_discount_ex_vat)
    : undefined;
  const discount = beforeDiscount === undefined || !pricePreview
    ? undefined
    : beforeDiscount - Number(showInclusive ? pricePreview.total_inc_vat : pricePreview.subtotal_ex_vat);

  useEffect(() => {
    setAmountTendered(totalIncLabel);
  }, [totalIncLabel]);

  const tenderedAmount = parsePriceInput(amountTendered) ?? totalInc;
  const changeAmount = Math.max(0, tenderedAmount - totalInc);
  const showChange = Boolean(pricePreview) && (tender === "cash" || tender === "eft");

  const addValid =
    canSell &&
    locationId &&
    skuId &&
    selectedSku?.is_sellable &&
    !selectedSku.is_archived &&
    numericQty > 0 &&
    (!selectedNeedsFloorStock || numericQty <= selectedRemaining) &&
    unitExVat(selectedSku ?? ({} as Sku), selectedCustomer, priceLists) > 0;

  const floorOnHandFor = useCallback(
    (id: string) =>
      inventoryBySku
        .get(id)
        ?.locations.find((loc) => loc.location_id === locationId)?.on_hand ?? 0,
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
        hasServicePrice: (sku) => unitExVat(sku, selectedCustomer, priceLists) > 0,
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
    [canSell, cartQtyBySku, floorOnHandFor, focusScanField, locationId, priceLists, selectedCustomer, skus],
  );

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      const target =
        event.target instanceof Element ? event.target : document.activeElement;
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
    !!pricePreview &&
    totalInc > 0 &&
    cart.length > 0 &&
    cart.every((line) => {
      if (!line.sku.is_sellable) return false;
      if (line.sku.is_archived) {
        const linked = linkedPickIds[line.sku.id] || pickId;
        return (
          canResumeArchivedTillPick(
            line.sku,
            tillPicks.find((item) => item.id === linked),
            line.qty,
            customerId,
          ) && cart.filter((item) => item.sku.id === line.sku.id).length === 1
        );
      }
      if (!requiresTillFloorStock(line.sku)) {
        return line.qty > 0;
      }
      const onHand =
        inventoryBySku
          .get(line.sku.id)
          ?.locations.find((loc) => loc.location_id === locationId)?.on_hand ??
        0;
      return line.qty > 0 && (cartQtyBySku.get(line.sku.id) ?? 0) <= onHand;
    });

  function addKnownProduct(sku: Sku, quantity: number): boolean {
    if (
      !cartReady ||
      !canSell ||
      !locationId ||
      sku.is_archived ||
      !sku.is_sellable ||
      (!sku.till_no_stock_required && !sku.retail_ex_vat) ||
      !Number.isFinite(quantity) ||
      quantity <= 0 ||
      unitExVat(sku, selectedCustomer, priceLists) <= 0
    )
      return false;
    const needsFloorStock = requiresTillFloorStock(sku);
    if (
      needsFloorStock &&
      quantity > floorOnHandFor(sku.id) - (cartQtyBySku.get(sku.id) ?? 0)
    ) {
      setError(tillScanErrorMessage("over_floor"));
      return false;
    }
    setError(null);
    setCart((current) => {
      const reserved = current
        .filter((line) => line.sku.id === sku.id)
        .reduce((sum, line) => sum + line.qty, 0);
      if (needsFloorStock && quantity > floorOnHandFor(sku.id) - reserved)
        return current;
      return mergeCartBySku(current, sku, quantity);
    });
    if (!sku.is_kit) focusScanField();
    return true;
  }

  function handleAddToCart() {
    if (!addValid || !selectedSku) return;
    if (addKnownProduct(selectedSku, numericQty)) {
      setSkuId("");
      setQty(1);
    }
  }

  function addProductFromBrowser(sku: Sku) {
    addKnownProduct(sku, 1);
  }

  function updateCartLine(
    key: string,
    patch: Partial<Pick<CartLine, "qty" | "discountPercent">>,
  ) {
    setCart((current) =>
      current.map((line) => {
        if (line.key !== key) {
          return line;
        }
        const nextQty = line.sku.is_archived
          ? line.qty
          : (patch.qty ?? line.qty);
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

  async function resumeExistingPick() {
    const pick = pendingTillPicks.find((item) => item.id === resumePickId);
    if (!pick?.kit_sku_id || !cartReady || resumingPick) return;
    setResumingPick(true);
    setError(null);
    try {
      const sku = await getSku(pick.kit_sku_id);
      const nextCustomerId = pick.customer_id || customerId;
      if (cart.some((line) => line.sku.id === sku.id))
        throw new Error(
          "This kit is already in the cart. Remove its current line before resuming this pick; quantities cannot be combined.",
        );
      if (cart.length > 0 && nextCustomerId !== customerId)
        throw new Error(
          "This pick belongs to another customer. Empty the cart or select that customer before resuming it.",
        );
      if (
        !sku.is_sellable ||
        !sku.is_kit ||
        (sku.is_archived &&
          !canResumeArchivedTillPick(
            sku,
            pick,
            pick.kit_qty ?? 0,
            nextCustomerId,
          ))
      )
        throw new Error(
          "This pick cannot be resumed. The kit must be sellable and its original, unconsumed till pick must predate archiving.",
        );
      const customer =
        nextCustomerId && !customers.some((item) => item.id === nextCustomerId)
          ? await getCustomer(nextCustomerId)
          : null;
      setCommitmentCustomer(customer);
      setCustomerId(nextCustomerId);
      setCart((current) => [
        ...current,
        { key: sku.id, sku, qty: pick.kit_qty ?? 0, discountPercent: 0 },
      ]);
      setLinkedPickIds((current) => ({ ...current, [sku.id]: pick.id }));
      setPickId(pick.id);
      setResumePickId("");
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Could not resume this pick.",
      );
    } finally {
      setResumingPick(false);
    }
  }

  async function handleCompleteSale() {
    if (!saleValid || !pricePreview) {
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
        ...priceRequest,
        price_revision: pricePreview.price_revision,
        tender,
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
      if (
        err instanceof ApiError && err.status === 409 &&
        err.detail && typeof err.detail === "object" &&
        "code" in err.detail && err.detail.code === "till_price_conflict"
      ) {
        refreshPrices();
      }
      if (
        err instanceof ApiError &&
        err.status === 409 &&
        isCreditBlockMessage(err.message)
      ) {
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
    setTillPicks((current) => [
      confirmed,
      ...current.filter((entry) => entry.id !== confirmed.id),
    ]);
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
      const message =
        err instanceof ApiError ? err.message : "Could not create the pick.";
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
      setPickDraft({
        ...pickDraft,
        error: "Acknowledge the split before confirming.",
      });
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
      const confirmed = await confirmPick(
        pickDraft.pick.id,
        requireAck ? true : undefined,
      );
      rememberConfirmedPick(pickDraft.kit, confirmed);
    } catch (err) {
      const message =
        err instanceof ApiError ? err.message : "Could not confirm the pick.";
      setPickDraft((current) =>
        current ? { ...current, confirming: false, error: message } : current,
      );
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
        <h1 className="cds--type-heading-05">Till</h1>
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
    <Stack gap={6} className={styles.page}>
      <div className="firstout-page-header">
        <div>
          <h1 className="cds--type-heading-05">Till</h1>
          <p className="cds--type-body-01">
            Process sales, returns, and payments.
          </p>
        </div>
        <div className="firstout-catalogue-actions">
          {can(user, "sales.returns") && (
            <Button
              kind="secondary"
              renderIcon={Undo}
              onClick={() => router.push("/returns")}
            >
              Process Return
            </Button>
          )}
          {can(user, "sales.laybys") && (
            <Button
              kind="secondary"
              renderIcon={Currency}
              onClick={() => router.push("/laybys?new=1")}
            >
              Layby Payment
            </Button>
          )}
          <Button
            kind="tertiary"
            renderIcon={Bookmark}
            disabled={!cartReady || loading || submitting}
            onClick={() => {
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
              router.push("/");
            }}
          >
            Hold sale
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
        <TillLoading mobileScan={mobileScan} paymentOptions={TENDER_OPTIONS} tender={tender} />
      ) : (
        <div className={styles.layout}>
          <div
            className={`firstout-section-accent firstout-tone-info ${styles.productBrowser}`}
          >
            <Stack gap={5}>
              <Tile>
                <Stack gap={5}>
                  <div className={styles.sectionHeading}>
                    <div>
                      <p className="cds--type-label-01">SHOWROOM PRODUCTS</p>
                      <h2 className="cds--type-heading-03">Find a product</h2>
                    </div>
                    <Tag type="blue">{vatBasisLabel(showInclusive)}</Tag>
                  </div>
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
                      labelText="Scan or type a barcode"
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
                    {mobileScan && (
                      <Button
                        kind="secondary"
                        renderIcon={Scan}
                        disabled={!locationId}
                        onClick={() => setScannerOpen(true)}
                      >
                        Scan
                      </Button>
                    )}
                  </div>

                  <div className="firstout-till-picker-row">
                    <ComboBox
                      id="till-sku"
                      titleText="Find by product, SKU or barcode"
                      placeholder="Search by SKU, barcode, or name..."
                      items={skuOptions}
                      itemToString={skuItemToString}
                      selectedItem={selectedSkuOption}
                      shouldFilterItem={filterSkuItem}
                      onChange={({ selectedItem }) =>
                        setSkuId(selectedItem?.id ?? "")
                      }
                      disabled={!locationId}
                      onInputChange={(value) => {
                        setProductQuery(value);
                        setProductPage(1);
                      }}
                    />
                    <Button
                      kind="tertiary"
                      onClick={() => router.push("/catalogue")}
                    >
                      Browse Catalogue
                    </Button>
                  </div>

                  <NumberInput
                    id="till-qty"
                    label="Quantity"
                    min={1}
                    max={
                      selectedSku?.till_no_stock_required
                        ? undefined
                        : selectedRemaining || undefined
                    }
                    value={qty}
                    onChange={(_, { value }) => {
                      if (value === "") {
                        setQty("");
                      } else {
                        setQty(
                          typeof value === "number" ? value : Number(value),
                        );
                      }
                    }}
                    helperText={
                      selectedSku && locationId
                        ? selectedSku.till_no_stock_required
                          ? "No stock needed"
                          : `${selectedRemaining} available at showroom`
                        : undefined
                    }
                    disabled={!skuId}
                  />

                  <Button
                    kind="secondary"
                    disabled={!addValid}
                    onClick={handleAddToCart}
                  >
                    Add to cart
                  </Button>
                  <div className={styles.productGrid}>
                    {visibleProducts.map((sku) => {
                      const remaining = Math.max(
                        0,
                        floorOnHandFor(sku.id) -
                          (cartQtyBySku.get(sku.id) ?? 0),
                      );
                      const priced = quoteSkuUnitExVat(
                        sku,
                        selectedCustomer,
                        priceLists,
                      );
                      return (
                        <ClickableTile
                          role="button"
                          key={sku.id}
                          aria-label={`Add ${sku.name} to sale`}
                          onClick={() => addProductFromBrowser(sku)}
                          disabled={
                            !cartReady ||
                            !canSell ||
                            !locationId ||
                            priced.unitExVat === null ||
                            priced.unitExVat <= 0 ||
                            (requiresTillFloorStock(sku) && remaining <= 0)
                          }
                        >
                          <div className={styles.productCard}>
                            <div className={styles.productPhoto}>
                              {sku.photo_storage_key ? (
                                <StaffImage
                                  src={skuPhotoUrl(sku.id)}
                                  alt=""
                                  className={styles.productImage}
                                />
                              ) : (
                                <ImageIcon size={32} aria-hidden />
                              )}
                            </div>
                            <h3 className="cds--type-heading-compact-01">
                              {sku.name}
                            </h3>
                            <p className="cds--type-label-01">{sku.our_ref}</p>
                            <div className={styles.priceRow}>
                              <p className="cds--type-body-01">
                                {priced.unitExVat === null
                                  ? "Price unavailable"
                                  : formatZarAmount(
                                      formatPriceAmount(
                                        displayUnitAmount(
                                          priced.unitExVat,
                                          showInclusive,
                                        ),
                                      ),
                                    )}
                              </p>
                              <Purchase size={20} aria-hidden />
                            </div>
                            <p className="cds--type-label-01">
                              {sku.is_kit
                                ? "Kit · parts checked at checkout"
                                : sku.till_no_stock_required
                                  ? "No stock needed"
                                  : `${formatQuantity(remaining)} available at showroom`}
                            </p>
                            {priced.warning && (
                              <p className="cds--type-label-01">
                                {priced.warning}
                              </p>
                            )}
                          </div>
                        </ClickableTile>
                      );
                    })}
                  </div>
                  {!browserProducts.length && (
                    <div className={styles.empty}>
                      <h3 className="cds--type-heading-03">
                        No matching products
                      </h3>
                      <p className="cds--type-body-01">
                        Try another product name or SKU, or choose a showroom
                        with available stock.
                      </p>
                    </div>
                  )}
                  <Pagination
                    page={browserPage}
                    pageSize={productPageSize}
                    pageSizes={[12, 24, 48]}
                    totalItems={browserProducts.length}
                    itemsPerPageText="Products per page:"
                    backwardText="Previous page"
                    forwardText="Next page"
                    onChange={({ page, pageSize }) => {
                      setProductPage(page);
                      setProductPageSize(pageSize);
                    }}
                  />
                  {pendingTillPicks.length > 0 && (
                    <Stack gap={3}>
                      <Select
                        id="till-resume-pick"
                        labelText="Resume an existing till pick"
                        value={resumePickId}
                        disabled={!cartReady || resumingPick || submitting}
                        onChange={(event) =>
                          setResumePickId(event.target.value)
                        }
                      >
                        <SelectItem value="" text="Select an existing pick" />
                        {pendingTillPicks.map((pick) => (
                          <SelectItem
                            key={pick.id}
                            value={pick.id}
                            text={`${pick.pick_number || pick.id} · ${pick.sku_our_ref} × ${pick.kit_qty}`}
                          />
                        ))}
                      </Select>
                      <p className="cds--type-helper-text-01">
                        An archived kit can finish its original pick at the
                        exact quantity. It stays unavailable for a new sale;
                        resuming does not restore the SKU.
                      </p>
                      <Button
                        kind="tertiary"
                        disabled={
                          !resumePickId ||
                          !cartReady ||
                          resumingPick ||
                          submitting ||
                          !canSell
                        }
                        onClick={() => void resumeExistingPick()}
                      >
                        {resumingPick ? "Resuming…" : "Resume existing pick"}
                      </Button>
                    </Stack>
                  )}
                </Stack>
              </Tile>
            </Stack>
          </div>

          <div
            className={`firstout-section-accent firstout-tone-info ${styles.sale}`}
          >
            <Tile>
              <Stack gap={5}>
                <div className={styles.sectionHeading}>
                  <h2 className="cds--type-heading-03">Current sale</h2>
                  <Tag type="gray">
                    {cart.length} product {cart.length === 1 ? "line" : "lines"}
                  </Tag>
                </div>
                <div className="firstout-till-picker-row">
                  <CustomerPicker
                    id="till-customer"
                    titleText="Customer (optional)"
                    customers={
                      commitmentCustomer?.id === customerId &&
                      !customers.some((item) => item.id === customerId)
                        ? [...customers, commitmentCustomer]
                        : customers
                    }
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

                <div>
                  <p className="cds--type-label-01">Pricing for this sale</p>
                  <p className="cds--type-body-01">
                    {classification} · {priceListName ?? "Catalogue tier"} · Unit prices {vatBasisLabel(showInclusive)}
                  </p>
                </div>
                {pricingError ? (
                  <Stack gap={3}>
                    <InlineNotification kind="error" title="Could not confirm sale prices" subtitle={pricingError} lowContrast hideCloseButton />
                    <div><Button kind="tertiary" size="sm" onClick={refreshPrices}>Check prices again</Button></div>
                  </Stack>
                ) : cart.length > 0 && !pricePreview ? (
                  <p role="status" className="cds--type-body-01">Checking sale prices…</p>
                ) : null}

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

                <section
                  aria-label="Products in current sale"
                  className={styles.cart}
                >
                  {cart.length === 0 ? (
                    <div className={styles.empty}>
                      <h3 className="cds--type-heading-compact-01">
                        Start a new sale
                      </h3>
                      <p className="cds--type-body-01">
                        Choose a product to add it here.
                      </p>
                    </div>
                  ) : (
                    cart.map((line, index) => {
                      const linePricing = pricePreview?.lines[index];
                      const priced = quoteSkuUnitExVat(
                        line.sku,
                        selectedCustomer,
                        priceLists,
                      );
                      const suspect = quoteLineSuspectWarning(
                        linePricing?.unit_ex_vat ?? "",
                        line.sku,
                        priced,
                        canViewCost,
                        showInclusive,
                      );
                      return (
                        <div className={styles.cartLine} key={line.key}>
                          <div className={styles.cartProduct}>
                            <SkuThumb sku={line.sku} />
                            <div>
                              <h3 className="cds--type-heading-compact-01">
                                {line.sku.name}
                              </h3>
                              <p className="cds--type-label-01">
                                {line.sku.our_ref}
                              </p>
                            </div>
                            <Button
                              kind="ghost"
                              size="sm"
                              hasIconOnly
                              renderIcon={TrashCan}
                              iconDescription={`Remove ${line.sku.name}`}
                              onClick={() => removeCartLine(line.key)}
                            />
                          </div>
                          {line.sku.is_archived && (
                            <p className="cds--type-label-01">
                              Archived kit: locked to its original pick
                              quantity. Remove the line to cancel this checkout.
                            </p>
                          )}
                          {!line.sku.is_sellable && (
                            <InlineNotification
                              kind="warning"
                              title="Not for sale"
                              subtitle="Remove this item to complete the sale."
                              lowContrast
                              hideCloseButton
                            />
                          )}
                          <div className={styles.cartControls}>
                            <NumberInput
                              id={`cart-qty-${line.key}`}
                              disabled={line.sku.is_archived}
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
                                updateCartLine(line.key, {
                                  qty: Math.max(1, next),
                                });
                              }}
                            />
                            {canDiscount && (
                              <NumberInput
                                id={`cart-discount-${line.key}`}
                                label="Discount (%)"
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
                                  updateCartLine(line.key, {
                                    discountPercent: clampDiscount(next),
                                  });
                                }}
                              />
                            )}
                          </div>
                          <div className={styles.priceRow}>
                            <p className="cds--type-label-01">
                              Unit ({vatBasisLabel(showInclusive)})
                            </p>
                            <p className="cds--type-body-01">
                              {money(linePricing && displayUnitAmount(Number(linePricing.unit_ex_vat), showInclusive))}
                            </p>
                          </div>
                          <div className={styles.priceRow}>
                            <p className="cds--type-label-01">
                              Line total incl. VAT
                            </p>
                            <p className="cds--type-heading-compact-01">
                              {money(linePricing?.inc_vat)}
                            </p>
                          </div>
                          {linePricing?.price_warning && (
                            <InlineNotification
                              kind="warning"
                              lowContrast
                              hideCloseButton
                              title="Price list or tier fallback"
                              subtitle={linePricing.price_warning}
                            />
                          )}
                          {suspect && (
                            <InlineNotification
                              kind="warning"
                              lowContrast
                              hideCloseButton
                              title="Check this price"
                              subtitle={suspect}
                            />
                          )}
                        </div>
                      );
                    })
                  )}
                </section>
                <h3 className="cds--type-heading-compact-01">Sale summary</h3>

                <dl className="firstout-sale-summary">
                  <div className="firstout-sale-summary__row">
                    <dt>{showInclusive ? "Subtotal (before discount, incl. VAT)" : "Subtotal (before discount, excl. VAT)"}</dt>
                    <dd>{money(beforeDiscount)}</dd>
                  </div>
                  <div className="firstout-sale-summary__row firstout-sale-summary__row--discount">
                    <dt>{showInclusive ? "Line discounts" : "Line discounts excl. VAT"}</dt>
                    <dd>{discount && discount > 0 ? "- " : ""}{money(discount)}</dd>
                  </div>
                  {!showInclusive && (
                    <div className="firstout-sale-summary__row">
                      <dt>Subtotal after discount excl. VAT</dt>
                      <dd>{money(pricePreview?.subtotal_ex_vat)}</dd>
                    </div>
                  )}
                  <div className="firstout-sale-summary__row">
                    <dt>VAT ({vatRateLabel}){showInclusive ? " included" : ""}</dt>
                    <dd>{money(pricePreview?.vat_amount)}</dd>
                  </div>
                  <div className="firstout-sale-summary__row firstout-sale-summary__row--total">
                    <dt>Total incl. VAT</dt>
                    <dd>{money(pricePreview?.total_inc_vat)}</dd>
                  </div>
                </dl>

                {confirmedPicks.length > 0 ? (
                  <Select
                    id="till-pick"
                    labelText="Existing till pick"
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

                {canOverrideCredit &&
                (selectedCustomer?.on_hold || creditBlock) ? (
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
                        onChange={(event) =>
                          setCreditOverrideReason(event.target.value)
                        }
                      />
                    ) : null}
                  </>
                ) : null}

                <RadioButtonGroup
                  legendText="Payment method"
                  name="till-tender"
                  valueSelected={tender}
                  onChange={(value) => setTender(value as TillTender)}
                  orientation="horizontal"
                >
                  {TENDER_OPTIONS.map((option) => (
                    <RadioButton
                      key={option.value}
                      id={`till-tender-${option.value}`}
                      value={option.value}
                      labelText={option.label}
                    />
                  ))}
                </RadioButtonGroup>

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
                    (creditOverride &&
                      canOverrideCredit &&
                      !creditOverrideReason.trim())
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

      {scannerOpen && mobileScan ? (
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
                  <StaffImage
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
                      {lastSale.prices_include_vat
                        ? "Unit incl. VAT"
                        : "Unit excl. VAT"}
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
                          <div className="firstout-muted-text">
                            {line.price_warning}
                          </div>
                        ) : null}
                        {line.suspect_price_warning ? (
                          <div className="firstout-price-warning">
                            {line.suspect_price_warning}
                          </div>
                        ) : null}
                      </TableCell>
                      <TableCell>{line.qty}</TableCell>
                      <TableCell>
                        {formatZarAmount(
                          lastSale.prices_include_vat
                            ? formatPriceAmount(
                                exVatToIncVat(Number(line.unit_ex_vat)),
                              )
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
              <p>
                Subtotal ex VAT: {formatZarAmount(lastSale.subtotal_ex_vat)}
              </p>
              <p>
                VAT ({vatRateLabel}): {formatZarAmount(lastSale.vat_amount)}
              </p>
              <p>
                <strong>
                  Total inc VAT: {formatZarAmount(lastSale.total_inc_vat)}
                </strong>
              </p>
              {!lastSale.lines[0]?.till_no_stock_required && (
                <p>
                  Floor stock remaining at {lastSale.location.location_name}:{" "}
                  {lastSale.location.on_hand}
                </p>
              )}
            </div>

            <ButtonSet>
              <Button
                kind="tertiary"
                onClick={() =>
                  void downloadInvoicePdf(
                    lastSale.invoice_id,
                    lastSale.invoice_number,
                  )
                }
              >
                Download PDF
              </Button>
              <Button
                kind="secondary"
                renderIcon={Undo}
                onClick={() =>
                  router.push(`/returns?invoice=${lastSale.invoice_id}`)
                }
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
          pickDraft?.confirming
            ? "Confirming…"
            : pickDraft?.creating
              ? "Creating…"
              : "Confirm pick"
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
              {pickDraft.kit.sku_name} ({pickDraft.kit.sku_code}) ×{" "}
              {pickDraft.kit.qty}. A pick tells the warehouse which storeroom
              each part comes from. The cart stays on the till.
            </p>
            {pickDraft.creating ? (
              <p className="cds--type-body-01">Creating the pick…</p>
            ) : null}
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
                    setPickDraft((current) =>
                      current ? { ...current, ack: !current.ack } : current,
                    )
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
