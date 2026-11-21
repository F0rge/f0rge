"use client";

import { StaffImage } from "@/components/staff-image";

import {
  Button,
  Checkbox,
  ClickableTile,
  ComboBox,
  InlineNotification,
  Link,
  Modal,
  NumberInput,
  Pagination,
  RadioButton,
  RadioButtonGroup,
  Select,
  SelectItem,
  Stack,
  Tab,
  TabList,
  TabPanel,
  TabPanels,
  Tabs,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableHeader,
  TableRow,
  Tag,
  TextArea,
  TextInput,
  Tile,
} from "@carbon/react";
import {
  Bookmark,
  Building,
  Currency,
  Image as ImageIcon,
  Launch,
  Location as LocationIcon,
  Locked,
  Money,
  Purchase,
  Receipt,
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
import styles from "./page.module.css";
import { TillLoading } from "./loading-layout";
import { HeldSalesWorkspace, useHeldSales } from "./held-sales-workspace";
import { TillPickList } from "./till-pick-list";
import { localIsoDate, statementDueDate } from "@/lib/till-statement";
import { commissionBase, rememberColleague, rememberedColleague, zar } from "@/lib/sales-staff";

import {
  ApiError,
  INVOICE_NOTE_MAX,
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
  getTillBasket,
  getCustomer,
  holdTillSale,
  resumeTillHeldSale,
  listPicks,
  exVatToIncVat,
  formatPriceAmount,
  formatZarAmount,
  isActiveLocation,
  listCustomers,
  listInventory,
  listLocations,
  listPriceLists,
  listSalesStaffOptions,
  listSkus,
  listTillReservations,
  parsePriceInput,
  previewTillPrices,
  settingsLogoUrl,
  skuPhotoUrl,
  updateTillBasket,
  type AppSettings,
  type CustomerCrm,
  type InventorySku,
  type HeldSale,
  type Location,
  type PriceList,
  type SalesStaffOption,
  type Sku,
  type PickDocument,
  type TillBasket,
  type TillPricePreview,
  type TillPriceRequest,
  type TillSaleResult,
  type TillReservation,
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
  nextTillStateAfterKitConfirm,
  openPicksHrefForKit,
  parseKitRequiresPick,
  salePickIds,
  type TillCartSnapshot,
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

import { workspaceIdentity } from "@/lib/record-workspace";
import { resetMainScroll } from "@/lib/reset-main-scroll";
import {
  basketContents,
  canKeepOriginalBasket,
  cartSnapshot,
  heldSaleRequest,
  isUncertainHeldResponse,
  type BasketContents,
  type PendingHeldOperation,
} from "@/lib/till-held-sales";
import { createBasketSaver, isBasketConflict } from "@/lib/till-basket";
import {
  basketConflict,
  conflictNotice,
  expiryNotice,
  tillAvailability,
  type BasketConflict,
} from "@/lib/till-reservations";
import { basketStockNote, resultStockState, type TillStock } from "@/lib/till-stock-notes";

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
  { value: "statement", label: "Pay on statement", icon: Receipt },
  { value: "card", label: "Card", icon: Purchase },
  { value: "cash", label: "Cash", icon: Money },
  { value: "eft", label: "EFT", icon: Building },
  { value: "deposit", label: "Layby Deposit", icon: Bookmark },
];

/** A search result; reserved SKUs stay listed but cannot be chosen. */
type SkuOption = Sku & { disabled?: boolean; reason?: string };

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

type RestoredCart = { lines: CartLine[]; customer: CustomerCrm | null };

const EMPTY_BASKET: BasketContents = { linked_pick_ids: {}, lines: [] };

async function hydrateCart(
  snapshot: TillCartSnapshot,
  skus: Sku[],
  picks: PickDocument[],
  customers: CustomerCrm[],
): Promise<RestoredCart> {
  const byId = await restoreTillCartSkus(snapshot, skus, picks, getSku);
  const lines = snapshot.lines.map((line) => {
    const sku = byId.get(line.skuId);
    if (!sku?.is_sellable) {
      throw new Error("A saved product is no longer available. Check the product and any linked kit pick before retrying.");
    }
    return { key: sku.id, sku, qty: line.qty, discountPercent: line.discountPercent };
  });
  const customer = snapshot.customerId
    ? customers.find((item) => item.id === snapshot.customerId) ?? await getCustomer(snapshot.customerId)
    : null;
  if (customer?.is_archived) throw new Error("The saved customer is archived.");
  return { lines, customer };
}

export default function TillPage() {
  const { user } = useAuth();
  return <TillWorkspace key={workspaceIdentity(user)} />;
}

function TillWorkspace() {
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
  const [pendingShowroom, setPendingShowroom] = useState<string | null>(null);
  const [resumedSale, setResumedSale] = useState(false);
  const [view, setView] = useState(0);
  const [heldNote, setHeldNote] = useState("");
  // The sale's invoice notes: printed on the invoice, and staff only.
  const [notePrinted, setNotePrinted] = useState("");
  const [noteInternal, setNoteInternal] = useState("");
  // Who made the sale (commission); defaults to this device's last choice.
  const [salesStaffId, setSalesStaffId] = useState("");
  const [colleagues, setColleagues] = useState<SalesStaffOption[] | null>(null);
  const [colleaguesError, setColleaguesError] = useState(false);
  const [heldNotice, setHeldNotice] = useState<{ title: string; subtitle?: string } | null>(null);
  const [heldFocus, setHeldFocus] = useState("");
  const [resumeDraft, setResumeDraft] = useState<HeldSale | null>(null);
  const [heldBusy, setHeldBusy] = useState(false);
  const [heldListBusy, setHeldListBusy] = useState(false);
  const [pendingHeld, setPendingHeld] = useState<PendingHeldOperation | null>(null);
  const [restoreBlocked, setRestoreBlocked] = useState(false);
  const [discardRestored, setDiscardRestored] = useState(false);
  const [pendingBlocked, setPendingBlocked] = useState(false);
  const [originalAvailable, setOriginalAvailable] = useState(false);
  const heldLock = useRef(false);
  // What the till says after showing the server's basket instead of its own.
  const [basketNotice, setBasketNotice] = useState<BasketConflict | null>(null);
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
  const [tender, setTender] = useState<TillTender>("statement");
  // A typed due date belongs to the customer it was typed for; a new customer gets their terms.
  const [dueDateEdit, setDueDateEdit] = useState<{ customerId: string; value: string } | null>(null);
  const [amountTendered, setAmountTendered] = useState("");
  const [loading, setLoading] = useState(true);
  const [loadSucceeded, setLoadSucceeded] = useState(false);
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
  // cartReady: the cart shows the server basket for this showroom and saves back to it.
  const [cartReady, setCartReady] = useState(false);
  const [expiresAt, setExpiresAt] = useState<string | null>(null);
  const [now, setNow] = useState(() => Date.now());
  // Active showroom and warehouse locations: the stock the company can sell.
  const [sellableLocationIds, setSellableLocationIds] = useState<ReadonlySet<string>>(() => new Set());
  const [reservations, setReservations] = useState<{ locationId: string; rows: TillReservation[] } | null>(null);
  const [reservationRevision, setReservationRevision] = useState(0);
  const refreshReservations = useCallback(() => setReservationRevision((revision) => revision + 1), []);
  // A basket a 409 carried; the restore effect shows it instead of fetching one.
  const incomingBasket = useRef<TillBasket | null>(null);
  const shownExpiry = useRef("");
  const adoptServerBasket = useCallback((failure: unknown) => {
    const conflict = basketConflict(failure) ?? { code: "basket_version_conflict" };
    incomingBasket.current = conflict.basket ?? null;
    if (conflict.code === "basket_expired") shownExpiry.current = conflict.basket?.expired_at ?? "";
    setBasketNotice(conflict);
    setCartReady(false);
  }, []);
  const [saver] = useState(() => createBasketSaver({
    put: (id, body) => updateTillBasket(id, body).then((saved) => {
      setExpiresAt(saved.expires_at ?? null);
      setNow(Date.now());
      refreshReservations();
      return saved;
    }),
    onConflict: adoptServerBasket,
    onError: (failure) => setError(failure instanceof Error ? failure.message : "Could not save the basket."),
  }));
  /** Show the server basket again; a basket conflict's own basket is shown without a fetch. */
  const reloadBasket = useCallback((conflict?: unknown) => {
    saver.reset(null);
    if (conflict !== undefined) adoptServerBasket(conflict);
    setCartReady(false);
  }, [adoptServerBasket, saver]);
  // Not gated on cartReady: reloading the basket after a hold or sale must not blank the list.
  const heldList = useHeldSales(canSell ? locationId : "");
  const heldLocked = heldBusy || heldListBusy || pendingHeld !== null;

  const currentSnapshot = useMemo<TillCartSnapshot>(() => ({
    locationId, customerId, pickId, linkedPickIds,
    ...(heldNote ? { note: heldNote } : {}),
    ...(notePrinted ? { notePrinted } : {}),
    ...(noteInternal ? { noteInternal } : {}),
    ...(salesStaffId ? { salesStaffId } : {}),
    lines: cart.map((line) => ({
      skuId: line.sku.id, qty: line.qty, discountPercent: line.discountPercent,
    })),
  }), [locationId, customerId, pickId, linkedPickIds, heldNote, notePrinted, noteInternal, salesStaffId, cart]);

  const applySnapshot = useCallback((snapshot: TillCartSnapshot, restored: RestoredCart) => {
    setCart(restored.lines);
    setCommitmentCustomer(restored.customer);
    setCustomerId(snapshot.customerId);
    if (snapshot.locationId) setLocationId(snapshot.locationId);
    setPickId(snapshot.pickId);
    setLinkedPickIds(snapshot.linkedPickIds);
    setHeldNote(snapshot.note ?? "");
    setNotePrinted(snapshot.notePrinted ?? "");
    setNoteInternal(snapshot.noteInternal ?? "");
    setSalesStaffId(snapshot.salesStaffId || rememberedColleague());
    setCartReady(true);
  }, []);

  useEffect(() => {
    if (!canSell) return;
    let live = true;
    listSalesStaffOptions()
      .then((rows) => { if (live) setColleagues(rows); })
      .catch(() => { if (live) setColleaguesError(true); });
    return () => { live = false; };
  }, [canSell]);

  const loadData = useCallback(async () => {
    setLoading(true);
    setLoadSucceeded(false);
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
      // Location types are showroom or warehouse; both count towards company stock.
      setSellableLocationIds(new Set(locationData.filter(isActiveLocation).map((loc) => loc.id)));
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
      setLoadSucceeded(true);
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
    // Any active location: stock not at this showroom is picked against the invoice.
    return (inventoryBySku.get(sku.id)?.locations ?? []).some(
      (loc) => loc.on_hand > 0 && sellableLocationIds.has(loc.location_id),
    );
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
  const reservationsBySku = useMemo(
    () => new Map((reservations?.locationId === locationId ? reservations.rows : [])
      .map((row) => [row.sku_id, row])),
    [locationId, reservations],
  );
  const availabilityFor = useCallback(
    (id: string) => tillAvailability({
      row: inventoryBySku.get(id),
      sellableLocationIds,
      reservation: reservationsBySku.get(id),
      inCart: cartQtyBySku.get(id) ?? 0,
    }),
    [cartQtyBySku, inventoryBySku, reservationsBySku, sellableLocationIds],
  );
  const showroomName = locations.find((loc) => loc.id === locationId)?.name ?? "this showroom";
  const stockFor = (id: string): TillStock => ({
    row: inventoryBySku.get(id),
    locationId,
    locationName: showroomName,
    sellableLocationIds,
    inCart: cartQtyBySku.get(id) ?? 0,
  });
  /** The one quiet stock line under a search result or tile. */
  const stockState = (sku: Sku) =>
    sku.is_kit
      ? "Kit · parts checked at checkout"
      : sku.till_no_stock_required
        ? "No stock needed"
        : resultStockState(stockFor(sku.id), availabilityFor(sku.id));
  const selectedAvailability = availabilityFor(skuId);
  const selectedRemaining = selectedAvailability.addable;
  const reservedReason = (sku: Sku) =>
    requiresTillFloorStock(sku) ? availabilityFor(sku.id).reason : null;
  const comboOptions: SkuOption[] = skuOptions.map((sku) => {
    const reason = reservedReason(sku);
    return reason ? { ...sku, disabled: true, reason } : sku;
  });
  const selectedSkuOption = comboOptions.find((sku) => sku.id === skuId) ?? null;

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
    if (!canSell || !loadSucceeded || !locationId || cartReady || restoreBlocked || pendingHeld) return;
    let cancelled = false;
    const incoming = incomingBasket.current;
    incomingBasket.current = null;
    void (async () => {
      const basket = incoming?.location_id === locationId ? incoming : await getTillBasket(locationId);
      if (cancelled) return;
      // Reset first so a basket that cannot be shown can still be discarded.
      saver.reset(basket);
      setExpiresAt(basket.expires_at ?? null);
      setNow(Date.now());
      if (basket.expired_at && !basket.lines.length && shownExpiry.current !== basket.expired_at) {
        shownExpiry.current = basket.expired_at;
        setBasketNotice({ code: "basket_expired", basket });
      }
      const snapshot = cartSnapshot(basket);
      try {
        const restored = await hydrateCart(snapshot, skus, tillPicks, customers);
        if (!cancelled) applySnapshot(snapshot, restored);
      } catch (failure) {
        if (!cancelled) setRestoreBlocked(true);
        throw failure;
      }
    })().catch((failure: unknown) => {
      if (!cancelled) setError(failure instanceof Error ? failure.message : "Could not restore the saved cart.");
    });
    return () => { cancelled = true; };
  }, [applySnapshot, canSell, cartReady, customers, loadSucceeded, locationId, pendingHeld, restoreBlocked, saver, skus, tillPicks]);

  useEffect(() => {
    if (cartReady && !pendingHeld) saver.save(basketContents(currentSnapshot, tillPicks));
  }, [cartReady, currentSnapshot, pendingHeld, saver, tillPicks]);

  useEffect(() => () => saver.dispose(), [saver]);

  useEffect(() => {
    if (!canSell || !loadSucceeded || !locationId) return;
    const controller = new AbortController();
    // ponytail: a failed refresh keeps the last list; the server re-checks every add.
    void listTillReservations(locationId, controller.signal).then((rows) => {
      if (!controller.signal.aborted) setReservations({ locationId, rows });
    }).catch(() => undefined);
    return () => controller.abort();
  }, [canSell, loadSucceeded, locationId, reservationRevision]);

  // Minute clock for the expiry notice; focus also refreshes other tills' reservations.
  useEffect(() => {
    const tick = () => {
      setNow(Date.now());
      // Expiry is lazy: fetching a lapsed basket empties it and the till says so.
      if (expiresAt && Date.parse(expiresAt) <= Date.now() && cartReady && !pendingHeld &&
          !submitting && !heldLock.current) reloadBasket();
    };
    const onFocus = () => {
      tick();
      refreshReservations();
    };
    const timer = expiresAt ? setInterval(tick, 60_000) : undefined;
    window.addEventListener("focus", onFocus);
    return () => {
      clearInterval(timer);
      window.removeEventListener("focus", onFocus);
    };
  }, [cartReady, expiresAt, pendingHeld, refreshReservations, reloadBasket, submitting]);

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

  const onStatement = tender === "statement";
  const saleDate = localIsoDate();
  const dueDate =
    dueDateEdit?.customerId === customerId
      ? dueDateEdit.value
      : statementDueDate(
          saleDate,
          selectedCustomer?.payment_terms_days,
          companySettings?.payment_terms_days,
        );
  const dueDateError = !onStatement
    ? null
    : !dueDate
      ? "Enter a due date."
      : dueDate < saleDate
        ? "The due date can't be before the issue date."
        : null;
  const creditOverrideActive = !onStatement && canOverrideCredit && creditOverride;

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

  const focusScanField = useCallback(() => {
    if (!isDesktopPointer()) {
      return;
    }
    document.getElementById("till-scan")?.focus();
  }, []);

  useEffect(() => {
    if (!loading && view === 0 && !heldLocked) {
      focusScanField();
    }
  }, [loading, focusScanField, heldLocked, view]);

  /** Other sales reserve this SKU's remaining stock: say why instead of adding it. */
  const showReserved = useCallback((sku: Sku): boolean => {
    if (!requiresTillFloorStock(sku) || !availabilityFor(sku.id).reason) return false;
    setError(null);
    setBasketNotice({
      code: "stock_reserved", sku_id: sku.id, blocking: reservationsBySku.get(sku.id)?.blocking ?? null,
    });
    return true;
  }, [availabilityFor, reservationsBySku]);

  const applyScan = useCallback(
    (code: string, allowOurRef: boolean, addQty = 1): boolean => {
      if (view !== 0 || heldLocked || heldLock.current || !cartReady || !canSell || !locationId) {
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
        floorOnHand: (id) => availabilityFor(id).limit,
        cartQty: (id) => cartQtyBySku.get(id) ?? 0,
        hasServicePrice: (sku) => unitExVat(sku, selectedCustomer, priceLists) > 0,
      });
      if (!result.ok) {
        const scanned = skus.find((sku) => sku.our_barcode === trimmed) ??
          (allowOurRef ? skus.find((sku) => sku.our_ref === trimmed) : undefined);
        if (scanned && showReserved(scanned)) return false;
        setError(tillScanErrorMessage(result.error));
        return false;
      }
      setError(null);
      setCart((current) => mergeCartBySku(current, result.sku, result.qty));
      setScanValue("");
      focusScanField();
      return true;
    },
    [availabilityFor, canSell, cartQtyBySku, cartReady, focusScanField, heldLocked, locationId, priceLists, selectedCustomer, showReserved, skus, view],
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

  const unavailableStock = resumedSale ? cart.filter((line) =>
    requiresTillFloorStock(line.sku) &&
    (cartQtyBySku.get(line.sku.id) ?? 0) > availabilityFor(line.sku.id).limit
  ) : [];

  const colleague = colleagues?.find((item) => item.id === salesStaffId);
  // Required once the business lists any active colleague; the server checks too.
  const colleagueChosen = !colleagues?.length || !!colleague;
  const saleValid =
    canSell &&
    colleagueChosen &&
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
      return line.qty > 0 && (cartQtyBySku.get(line.sku.id) ?? 0) <= availabilityFor(line.sku.id).limit;
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
    const { limit, addable } = availabilityFor(sku.id);
    if (needsFloorStock && quantity > addable) {
      if (!showReserved(sku)) setError(tillScanErrorMessage("over_floor"));
      return false;
    }
    setError(null);
    setCart((current) => {
      const reserved = current
        .filter((line) => line.sku.id === sku.id)
        .reduce((sum, line) => sum + line.qty, 0);
      if (needsFloorStock && quantity > limit - reserved)
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
    const skuId = cart.find((line) => line.key === key)?.sku.id;
    if (!skuId) return;
    setCart((current) => current.filter((line) => line.key !== key));
    setLinkedPickIds((current) => Object.fromEntries(
      Object.entries(current).filter(([id]) => id !== skuId),
    ));
    if (linkedPickIds[skuId] === pickId ||
        tillPicks.some((pick) => pick.id === pickId && pick.kit_sku_id === skuId)) {
      setPickId("");
    }
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

  async function changeShowroom(next: string) {
    setPendingShowroom(null);
    if (heldLock.current) return;
    heldLock.current = true;
    setHeldBusy(true);
    try {
      // Changing showroom clears the cart, so leave this showroom's basket empty.
      saver.save(EMPTY_BASKET);
      await saver.flush();
    } catch {
      // The save callbacks report a rejected save; the old showroom keeps its basket.
    } finally {
      heldLock.current = false;
      setHeldBusy(false);
    }
    reloadBasket();
    setRestoreBlocked(false);
    setLocationId(next);
    setSkuId("");
    setCart([]);
    setResumedSale(false);
    setPickId("");
    setLinkedPickIds({});
    setKitBlocks([]);
    setCreditBlock(null);
    setHeldNote("");
    setNotePrinted("");
    setNoteInternal("");
    setHeldNotice(null);
    setBasketNotice(null);
    setHeldFocus("");
  }

  function showView(next: number) {
    if (next === 1 && view !== 1) heldList.refresh();
    setView(next);
    resetMainScroll();
  }

  async function restoreHeldDestination(snapshot: TillCartSnapshot) {
    const [latestSkus, latestPicks, latestInventory] = await Promise.all([
      listSkus(), listPicks("till"), listInventory(),
    ]);
    await hydrateCart(snapshot, latestSkus, latestPicks, []);
    return { latestSkus, latestPicks, latestInventory };
  }

  async function finishHeldOperation(
    operation: PendingHeldOperation,
    destination: Awaited<ReturnType<typeof restoreHeldDestination>> | null,
    retry: boolean,
  ) {
    let acknowledged = false;
    try {
      if (operation.kind === "hold") {
        const draft = await holdTillSale(operation.request);
        acknowledged = true;
        // The server emptied the basket with the hold and released its stock.
        reloadBasket();
        refreshReservations();
        setResumedSale(false);
        setHeldFocus(draft.id);
        setHeldNotice({ title: `${draft.reference} is on hold`, subtitle: "Choose Resume sale when you’re ready." });
        showView(1);
      } else {
        const result = await resumeTillHeldSale(operation.id, operation.request);
        acknowledged = true;
        if (result.resumed_id !== operation.id || !result.basket ||
            (result.held_current_id ?? null) !== (operation.request.current?.id ?? null)) {
          throw new Error("The till could not confirm which basket was resumed.");
        }
        const next = destination ?? await restoreHeldDestination(operation.destination);
        const snapshot = cartSnapshot(result.basket);
        const restored = await hydrateCart(snapshot, next.latestSkus, next.latestPicks, []);
        setSkus(next.latestSkus.filter((sku) => !sku.is_archived));
        setTillPicks(next.latestPicks);
        setInventory(next.latestInventory);
        saver.reset(result.basket);
        setExpiresAt(result.basket.expires_at ?? null);
        refreshReservations();
        applySnapshot(snapshot, restored);
        setResumedSale(true);
        setTender("statement");
        setCreditOverride(false);
        setCreditOverrideReason("");
        refreshPrices();
        setHeldNotice({
          title: `${operation.reference} resumed`,
          subtitle: result.held_current_id
            ? "The previous basket is on hold. Review prices and stock before taking payment."
            : "Review prices and stock before taking payment.",
        });
        showView(0);
      }
      setLastSale(null);
      setSkuId("");
      setQty(1);
      setKitBlocks([]);
      setCreditBlock(null);
      setRestoreBlocked(false);
      setPendingHeld(null);
      setPendingBlocked(false);
      setOriginalAvailable(false);
      heldList.refresh();
    } catch (failure: unknown) {
      if (!acknowledged && isBasketConflict(failure)) {
        // Expired, reserved elsewhere or changed: show the server basket and say why.
        setPendingHeld(null);
        reloadBasket(failure);
        heldList.refresh();
        return;
      } else if (!acknowledged && basketConflict(failure)?.code === "held_sale_expired") {
        // The server deleted it and released its stock; the current basket is untouched.
        setPendingHeld(null);
        setBasketNotice(basketConflict(failure));
        heldList.refresh();
        return;
      } else if (!acknowledged && !retry && !isUncertainHeldResponse(failure)) {
        setPendingHeld(null);
        heldList.refresh();
      } else if (acknowledged || !isUncertainHeldResponse(failure)) {
        setPendingBlocked(true);
        setOriginalAvailable(!acknowledged && retry && canKeepOriginalBasket(failure, operation));
      }
      setError(failure instanceof Error ? failure.message : "Could not confirm the held sale operation.");
    }
  }

  async function startHeldOperation(draft?: HeldSale) {
    if (!cartReady || !loadSucceeded || !locationId || heldLocked || heldLock.current || submitting || resumingPick || pickDraft) return;
    if (draft ? draft.location_id !== locationId : !currentSnapshot.lines.length) return;
    heldLock.current = true;
    setHeldBusy(true);
    setError(null);
    try {
      const basket = await saver.flush();
      const destination = draft ? cartSnapshot(draft) : null;
      const prepared = destination ? await restoreHeldDestination(destination) : null;
      const operation: PendingHeldOperation = draft && destination ? {
        kind: "resume",
        id: draft.id,
        reference: draft.reference,
        startedAt: Date.now(),
        request: {
          version: draft.version,
          location_id: locationId,
          operation_id: crypto.randomUUID(),
          basket_id: basket.id,
          ...(currentSnapshot.lines.length ? { current: heldSaleRequest(currentSnapshot, tillPicks) } : {}),
        },
        destination,
      } : { kind: "hold", request: { ...heldSaleRequest(currentSnapshot, tillPicks), basket_id: basket.id } };
      setPendingHeld(operation);
      setPendingBlocked(false);
      setResumeDraft(null);
      await finishHeldOperation(operation, prepared, false);
    } catch (failure: unknown) {
      // The saver already showed the server basket for a basket conflict.
      if (!isBasketConflict(failure)) {
        setError(failure instanceof Error ? failure.message : "Could not prepare the held sale.");
      }
    } finally {
      heldLock.current = false;
      setHeldBusy(false);
    }
  }

  async function retryHeldOperation() {
    if (!pendingHeld || heldLock.current) return;
    heldLock.current = true;
    setHeldBusy(true);
    setError(null);
    setOriginalAvailable(false);
    try {
      await finishHeldOperation(pendingHeld, null, true);
    } finally {
      heldLock.current = false;
      setHeldBusy(false);
    }
  }

  /** The resume did not happen, so the server basket still holds the original sale. */
  function keepOriginalBasket() {
    if (!originalAvailable || heldLock.current) return;
    setPendingHeld(null);
    setPendingBlocked(false);
    setOriginalAvailable(false);
    setError(null);
    setHeldNotice({ title: "Current basket kept" });
    showView(0);
    reloadBasket();
    heldList.refresh();
  }

  async function handleCompleteSale() {
    if (!saleValid || !pricePreview || !cartReady || heldLocked || heldLock.current || submitting) {
      return;
    }
    if (creditOverrideActive && !creditOverrideReason.trim()) {
      setError("Override reason is required.");
      return;
    }
    if (dueDateError) {
      setError(dueDateError);
      return;
    }
    setSubmitting(true);
    setError(null);
    setCreditBlock(null);
    setKitBlocks([]);
    setLastSale(null);
    try {
      const pickIds = salePickIds(linkedPickIds, pickId);
      const basket = await saver.flush();
      const result = await createTillSale({
        location_id: locationId,
        basket_id: basket.id,
        basket_version: basket.version,
        ...priceRequest,
        price_revision: pricePreview.price_revision,
        tender,
        ...(onStatement ? { due_date: dueDate } : {}),
        ...(notePrinted.trim() ? { note_printed: notePrinted.trim() } : {}),
        ...(noteInternal.trim() ? { note_internal: noteInternal.trim() } : {}),
        ...(colleague ? { sales_staff_id: colleague.id } : {}),
        ...(pickId ? { pick_id: pickId } : {}),
        ...(pickIds.length > 0 ? { pick_ids: pickIds } : {}),
        ...(creditOverrideActive
          ? {
              credit_override: true,
              credit_override_reason: creditOverrideReason.trim(),
            }
          : {}),
      });
      setLastBuyerName(selectedCustomer?.name ?? WALK_IN_CUSTOMER_NAME);
      setLastSale(result);
      setCart([]);
      setResumedSale(false);
      setSkuId("");
      setCustomerId("");
      setDueDateEdit(null);
      setPickId("");
      setLinkedPickIds({});
      setKitBlocks([]);
      setHeldNote("");
      setNotePrinted("");
      setNoteInternal("");
      setHeldNotice(null);
      setBasketNotice(null);
      // The server emptied the basket with the sale.
      reloadBasket();
      setQty(1);
      await loadData();
    } catch (err) {
      if (isBasketConflict(err)) {
        // Expired, reserved elsewhere or changed: show the server basket and say why.
        reloadBasket(err);
        return;
      }
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

  async function openPicksForKit(kit: TillKitBlock) {
    try {
      await saver.flush();
    } catch {
      setError("This browser could not save the cart. Keep the till open while you finish the sale.");
      return;
    }
    router.push(openPicksHrefForKit(kit));
  }

  async function discardSavedCart() {
    if (!pendingHeld) {
      try {
        saver.save(EMPTY_BASKET);
        await saver.flush();
      } catch {
        setError("This browser could not update the saved cart.");
        return;
      }
    }
    setDiscardRestored(false);
    setRestoreBlocked(false);
    setPendingHeld(null);
    setPendingBlocked(false);
    setOriginalAvailable(false);
    setResumedSale(false);
    setHeldNotice(null);
    setError(null);
    reloadBasket();
    heldList.refresh();
  }

  const basketMessage = basketNotice &&
    conflictNotice(basketNotice, (id) => skus.find((sku) => sku.id === id)?.name);
  const saleExpiry = cart.length > 0 && expiresAt
    ? expiryNotice(expiresAt, now, companySettings?.till_hold_hours)
    : null;

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
            disabled={!cartReady || loading || submitting || heldLocked || resumingPick || !!pickDraft || cart.length === 0}
            onClick={() => void startHeldOperation()}
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

      {basketMessage && <InlineNotification kind={basketMessage.kind} lowContrast title={basketMessage.title}
        subtitle={basketMessage.subtitle} onCloseButtonClick={() => setBasketNotice(null)} />}
      {heldNotice && <InlineNotification kind="success" lowContrast title={heldNotice.title}
        subtitle={heldNotice.subtitle} onCloseButtonClick={() => setHeldNotice(null)} />}
      {pendingHeld && <div>
        <InlineNotification kind="warning" lowContrast hideCloseButton title="Held sale operation pending"
          subtitle="Retry to confirm the result before changing the cart or taking payment." />
        <Button kind="tertiary" disabled={heldBusy} onClick={() => void retryHeldOperation()}>
          {heldBusy ? "Confirming…" : "Retry held sale operation"}
        </Button>
        {originalAvailable && <Button kind="secondary" disabled={heldBusy}
          onClick={keepOriginalBasket}>Keep current basket</Button>}
        {pendingBlocked && <Button kind="danger--ghost" disabled={heldBusy}
          onClick={() => setDiscardRestored(true)}>Discard recovery copy</Button>}
      </div>}
      {restoreBlocked && !pendingHeld && <div>
        <InlineNotification kind="warning" lowContrast hideCloseButton title="Saved cart needs attention"
          subtitle="Your saved basket could not be loaded as it is. Reload after correcting the issue, or discard the saved cart to start again." />
        <Button kind="danger--ghost" onClick={() => setDiscardRestored(true)}>Discard saved cart</Button>
      </div>}
      <Modal open={discardRestored} danger
        modalHeading={pendingHeld ? "Discard the recovery copy?" : "Discard the saved cart?"}
        primaryButtonText={pendingHeld ? "Discard recovery copy" : "Discard cart"}
        secondaryButtonText="Keep cart" shouldSubmitOnEnter={false}
        onRequestClose={() => setDiscardRestored(false)} onRequestSubmit={() => void discardSavedCart()}>
        <p>{pendingHeld
          ? "This clears the unfinished cart. Check Held sales for any baskets already saved there."
          : "This empties your saved basket for this showroom."}</p>
      </Modal>
      <Modal open={resumeDraft !== null} modalHeading={`Resume ${resumeDraft?.reference ?? "held sale"}?`}
        primaryButtonText={heldBusy ? "Resuming…" : "Hold current and resume"} primaryButtonDisabled={heldBusy}
        secondaryButtonText="Cancel" preventCloseOnClickOutside
        onRequestClose={() => { if (!heldBusy) setResumeDraft(null); }}
        onRequestSubmit={() => { if (resumeDraft) void startHeldOperation(resumeDraft); }}>
        {error && resumeDraft && <InlineNotification kind="error" lowContrast hideCloseButton
          title="Could not resume the held sale" subtitle={error} />}
        <p>The current basket will go into Held sales. The selected basket will become the current sale.</p>
      </Modal>

      <Tabs selectedIndex={view} onChange={({ selectedIndex }) => showView(selectedIndex)}>
        <TabList aria-label="Till views">
          <Tab disabled={heldBusy || heldListBusy || submitting || resumingPick}>Current sale</Tab>
          <Tab disabled={heldBusy || heldListBusy || submitting || resumingPick}>
            Held sales{heldList.loading || heldList.error ? "" : ` (${heldList.sales.length})`}
          </Tab>
        </TabList>
        <TabPanels>
          <TabPanel className="held-sales-panel">
            <div className="held-sales-content" inert={heldLocked} aria-busy={heldBusy || undefined}>
      {resumedSale && cart.length > 0 && (
        <InlineNotification kind="info" lowContrast hideCloseButton title="Resumed sale"
          subtitle="Check the payment method, prices and available stock before completing the sale." />
      )}
      {unavailableStock.length > 0 && <InlineNotification kind="warning" lowContrast hideCloseButton
        title="Not enough stock"
        subtitle={`Review the quantities for ${unavailableStock.map((line) => line.sku.our_ref).join(", ")} before taking payment.`} />}

      <Modal
        open={pendingShowroom !== null}
        modalHeading="Change showroom?"
        primaryButtonText="Change showroom"
        secondaryButtonText="Keep current sale"
        danger
        onRequestClose={() => setPendingShowroom(null)}
        onRequestSubmit={() => {
          if (pendingShowroom !== null) void changeShowroom(pendingShowroom);
        }}
      >
        <p>Changing the showroom will clear the current cart.</p>
      </Modal>

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
            <Button kind="ghost" onClick={() => void openPicksForKit(kit)}>
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
                      const next = event.target.value;
                      if (next === locationId) return;
                      if (cart.length) {
                        setPendingShowroom(next);
                      } else {
                        void changeShowroom(next);
                      }
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
                      items={comboOptions}
                      itemToString={skuItemToString}
                      itemToElement={(item) => item.reason ? (
                        <span className={styles.reserved}>
                          <Locked size={16} aria-hidden />
                          <span>{skuItemToString(item)} · {item.reason}</span>
                        </span>
                      ) : (
                        <span>
                          {skuItemToString(item)}
                          <span className={styles.stockState}> · {stockState(item)}</span>
                        </span>
                      )}
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
                        ? stockState(selectedSku)
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
                      const remaining = availabilityFor(sku.id).addable;
                      const reason = reservedReason(sku);
                      const priced = quoteSkuUnitExVat(
                        sku,
                        selectedCustomer,
                        priceLists,
                      );
                      return (
                        <ClickableTile
                          role="button"
                          key={sku.id}
                          aria-label={`Add ${sku.name} to sale${reason ? `. ${reason}` : ""}`}
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
                            {reason ? (
                              <p className={`cds--type-label-01 ${styles.reserved}`}>
                                <Locked size={16} aria-hidden />
                                {reason}
                              </p>
                            ) : (
                              <p className={`cds--type-label-01 ${styles.stockState}`}>
                                {stockState(sku)}
                              </p>
                            )}
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
                {saleExpiry && (
                  <InlineNotification kind={saleExpiry.kind} lowContrast hideCloseButton
                    title={saleExpiry.title} subtitle={saleExpiry.subtitle} />
                )}
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
                {colleagues?.length ? (
                  <Select
                    id="till-sales-colleague"
                    labelText="Sales colleague"
                    value={colleague?.id ?? ""}
                    invalid={cart.length > 0 && !colleague}
                    invalidText="Choose who made this sale"
                    helperText={colleague ? `Counts towards ${colleague.short_name || colleague.name.split(/\s+/)[0]}'s commission: ${zar(commissionBase(cart.map((line, index) => ({
                      excluded: !!line.sku.exclude_from_commission,
                      exVat: pricePreview?.lines[index]?.ex_vat,
                    }))))} excl. VAT` : undefined}
                    onChange={(event) => {
                      setSalesStaffId(event.target.value);
                      rememberColleague(event.target.value);
                    }}
                  >
                    <SelectItem value="" text="Who made this sale?" disabled />
                    {colleagues.map((item) => (
                      <SelectItem key={item.id} value={item.id} text={item.name} />
                    ))}
                  </Select>
                ) : colleaguesError ? (
                  <InlineNotification
                    kind="warning"
                    title="Sales colleagues could not be loaded"
                    subtitle="Reload the till to choose who made this sale."
                    hideCloseButton
                    lowContrast
                  />
                ) : null}

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
                      const stockNote = requiresTillFloorStock(line.sku)
                        ? basketStockNote(stockFor(line.sku.id))
                        : null;
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
                              <Link
                                className="cds--type-label-01"
                                href={`/catalogue/${line.sku.id}`}
                                target="_blank"
                                rel="noopener"
                                renderIcon={Launch}
                                aria-label={`Open ${line.sku.our_ref} in a new tab`}
                              >
                                {line.sku.our_ref}
                              </Link>
                              {stockNote && (
                                <p className={`cds--type-helper-text-01 ${styles.reserved} ${styles.stockState}`}>
                                  <LocationIcon size={16} aria-hidden />
                                  {stockNote}
                                </p>
                              )}
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
                              max={
                                requiresTillFloorStock(line.sku)
                                  ? availabilityFor(line.sku.id).limit || undefined
                                  : undefined
                              }
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
                  {cart.some((line) => requiresTillFloorStock(line.sku)) && (
                    <p className={`cds--type-helper-text-01 ${styles.stockState}`}>
                      Stock notes are for staff only and are not printed on the invoice.
                    </p>
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

                <TextArea
                  id="till-note-printed"
                  labelText="Note on invoice"
                  helperText="Printed on the invoice the customer receives."
                  rows={2}
                  maxCount={INVOICE_NOTE_MAX}
                  enableCounter
                  value={notePrinted}
                  onChange={(event) => setNotePrinted(event.target.value)}
                />
                <TextArea
                  id="till-note-internal"
                  labelText="Internal note"
                  helperText="Staff only. Never printed."
                  rows={2}
                  maxCount={INVOICE_NOTE_MAX}
                  enableCounter
                  value={noteInternal}
                  onChange={(event) => setNoteInternal(event.target.value)}
                />

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

                {!onStatement &&
                canOverrideCredit &&
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

                {onStatement ? (
                  <>
                    <TextInput
                      id="till-due-date"
                      labelText="Due date"
                      type="date"
                      min={saleDate}
                      value={dueDate}
                      onChange={(event) =>
                        setDueDateEdit({ customerId, value: event.target.value })
                      }
                      invalid={Boolean(dueDateError)}
                      invalidText={dueDateError ?? undefined}
                      helperText={
                        selectedCustomer?.payment_terms_days != null
                          ? `${selectedCustomer.name} has ${selectedCustomer.payment_terms_days}-day terms.`
                          : `${companySettings?.payment_terms_days ?? 30} days, the company's payment terms.`
                      }
                    />
                    <InlineNotification
                      kind="info"
                      lowContrast
                      hideCloseButton
                      title="No payment is recorded now."
                      subtitle="The invoice shows as On statement until someone records a payment on it."
                    />
                  </>
                ) : (
                  <TextInput
                    id="till-amount-tendered"
                    labelText="Amount Tendered"
                    value={amountTendered}
                    onChange={(event) => setAmountTendered(event.target.value)}
                  />
                )}

                {showChange ? (
                  <p className="firstout-muted-text">
                    Change: {formatZarAmount(formatPriceAmount(changeAmount))}
                  </p>
                ) : null}

                <Button
                  kind="primary"
                  disabled={
                    !saleValid ||
                    !cartReady ||
                    heldLocked ||
                    submitting ||
                    Boolean(dueDateError) ||
                    (creditOverrideActive && !creditOverrideReason.trim())
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
              {lastSale.payment_number ? (
                <p>
                  Payment {lastSale.payment_number} — {lastSale.tender}
                </p>
              ) : (
                <p>
                  <Tag type="purple" size="sm">
                    On statement
                  </Tag>{" "}
                  {formatZarAmount(lastSale.total_inc_vat)} owing
                  {lastSale.due_date ? `, due ${lastSale.due_date}` : ""}
                </p>
              )}
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

            {lastSale.on_account ? (
              <p className="cds--type-helper-text-01">
                When the customer pays, open the invoice and choose Record payment.
              </p>
            ) : null}

            <div className="firstout-catalogue-actions">
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
              {lastSale.pick_id && (
                <Button kind="ghost" href="#pick-list">
                  View pick list
                </Button>
              )}
            </div>
          </Stack>
        </Tile>
      ) : null}
      {lastSale?.pick_id && (
        <TillPickList
          key={lastSale.pick_id}
          pickId={lastSale.pick_id}
          showroomId={lastSale.location.location_id}
          noStockLabels={lastSale.lines
            .filter((line) => line.till_no_stock_required)
            .map((line) => {
              const ref = skus.find((sku) => sku.id === line.sku_id)?.our_ref;
              return ref ? `${line.description} (${ref})` : line.description;
            })}
          onNewSale={() => {
            setLastSale(null);
            resetMainScroll();
            focusScanField();
          }}
        />
      )}

            </div>
          </TabPanel>
          <TabPanel className="held-sales-panel">
            <div className="held-sales-content">
              {view === 1 && <HeldSalesWorkspace
                key={`${locationId}:${heldFocus}`}
                locationId={locationId}
                holdHours={companySettings?.till_hold_hours}
                showroom={locations.find((location) => location.id === locationId)?.name ?? ""}
                list={heldList}
                focusId={heldFocus}
                busy={heldLocked || submitting || !cartReady}
                onBusy={setHeldListBusy}
                onNotice={(title, subtitle) => setHeldNotice({ title, subtitle })}
                onResume={(draft) => {
                  setError(null);
                  if (cart.length) setResumeDraft(draft);
                  else void startHeldOperation(draft);
                }}
              />}
            </div>
          </TabPanel>
        </TabPanels>
      </Tabs>

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
