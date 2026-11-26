"use client";

import { StaffImage } from "@/components/staff-image";

import {
  Button,
  Checkbox,
  InlineNotification,
  Modal,
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
  TextInput,
  Tile,
} from "@carbon/react";
import {
  Bookmark,
  Building,
  Currency,
  Location as LocationIcon,
  Money,
  Purchase,
  Receipt,
  Scan,
  Undo,
} from "@carbon/icons-react";
import { useQueries, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter, useSearchParams } from "next/navigation";
import {
  Suspense,
  useCallback,
  useEffect,
  useEffectEvent,
  useMemo,
  useReducer,
  useRef,
  useState,
  useSyncExternalStore,
} from "react";

import {
  CartEditor,
  mergeCartBySku,
  clampDiscount,
  type CartLine,
} from "@/components/cart-editor";
import { TillScanner } from "@/components/till-scanner";
import {
  getMobileScanServerSnapshot,
  getMobileScanSnapshot,
  subscribeMobileScan,
} from "@/lib/mobile-scan";
import styles from "@/components/cart-editor.module.css";
import { TillLoading } from "./loading-layout";
import { HeldSalesWorkspace, useHeldSales } from "./held-sales-workspace";
import { TillPickList } from "./till-pick-list";
import { localIsoDate } from "@/lib/dates";
import { statementDueDate } from "@/lib/till-statement";
import { rememberedColleague } from "@/lib/sales-staff";
import { anyLineBlocked, formatDiscount, mayBePriced } from "@/lib/sale-preview";
import type { QuantityRuleRefusal } from "@/lib/sale-quantity-rule";

import {
  ApiError,
  can,
  canManageCustomerCredit,
  canUseTill,
  cancelPick,
  confirmPick,
  createPick,
  createTillSale,
  downloadInvoicePdf,
  getQuote,
  getSku,
  getTillBasket,
  getCustomer,
  holdTillSale,
  resumeTillHeldSale,
  listPicks,
  formatPriceAmount,
  formatZarAmount,
  isActiveLocation,
  listInventory,
  listSkus,
  listTillReservations,
  parsePriceInput,
  previewTillPrices,
  settingsLogoUrl,
  updateTillBasket,
  vatPercentLabel,
  type CustomerCrm,
  type HeldSale,
  type Location,
  type Sku,
  type PickDocument,
  type Quote,
  type TillBasket,
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
import { queryKeys, referenceQueries, stockQueries } from "@/lib/queries";
import {
  completeTillSale,
  creditOverrideActive as isCreditOverrideActive,
  EMPTY_SALE,
  tillPriceRequest,
  tillSaleReducer,
  type TillSale,
} from "@/lib/till-sale";
import {
  nextTillStateAfterKitConfirm,
  openPicksHrefForKit,
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

type RestoredCart = { lines: CartLine[]; customer: CustomerCrm | null };

const EMPTY_BASKET: BasketContents = { linked_pick_ids: {}, lines: [] };
const NONE: never[] = [];
const PRICE_PREVIEW_KEY = ["till", "price-preview"] as const;

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
  return (
    <Suspense fallback={<TillLoading paymentOptions={TENDER_OPTIONS} tender="statement" />}>
      <TillWorkspace key={workspaceIdentity(user)} />
    </Suspense>
  );
}

function TillWorkspace() {
  const router = useRouter();
  // "Open in till" on a quote: /till?quote=<id>.
  const quoteParam = useSearchParams().get("quote") ?? "";
  const mobileScan = useSyncExternalStore(
    subscribeMobileScan,
    getMobileScanSnapshot,
    getMobileScanServerSnapshot,
  );
  const { user } = useAuth();
  const canSell = canUseTill(user);
  const canDiscount = can(user, "till.discount");
  const canOverrideCredit = canManageCustomerCredit(user);
  const client = useQueryClient();
  const loaded = Boolean(user);
  const tillData = useQueries({
    queries: [
      { ...referenceQueries.locations, enabled: loaded },
      { ...referenceQueries.skus, enabled: loaded },
      { ...stockQueries.inventory, enabled: loaded },
      { ...referenceQueries.customers, enabled: loaded },
      { ...referenceQueries.settings, enabled: loaded },
      { ...stockQueries.tillPicks, enabled: loaded },
      { ...referenceQueries.priceLists, enabled: loaded },
    ],
  });
  const [locationsQuery, skusQuery, inventoryQuery, customersQuery, settingsQuery, picksQuery, priceListsQuery] = tillData;
  const loadSucceeded = tillData.every((query) => query.data !== undefined);
  const loadError = loadSucceeded ? null : tillData.find((query) => query.error)?.error ?? null;
  const loading = !loadSucceeded && !loadError;
  const allLocations = locationsQuery.data;
  const locations = useMemo(
    () => (allLocations ?? NONE).filter((loc: Location) => isActiveLocation(loc) && loc.type === "showroom"),
    [allLocations],
  );
  // Location types are showroom or warehouse; both count towards company stock.
  const sellableLocationIds = useMemo<ReadonlySet<string>>(
    () => new Set((allLocations ?? NONE).filter(isActiveLocation).map((loc: Location) => loc.id)),
    [allLocations],
  );
  const allSkus = skusQuery.data;
  const skus = useMemo(() => (allSkus ?? NONE).filter((sku: Sku) => !sku.is_archived), [allSkus]);
  const inventory = inventoryQuery.data ?? NONE;
  const customers = customersQuery.data ?? NONE;
  const companySettings = settingsQuery.data ?? null;
  const tillPicks = picksQuery.data ?? NONE;
  const priceLists = priceListsQuery.data ?? NONE;
  const colleaguesQuery = useQuery({ ...referenceQueries.salesStaffOptions, enabled: canSell });
  const colleagues = colleaguesQuery.data ?? null;
  const colleaguesError = colleaguesQuery.isError;
  const [sale, dispatch] = useReducer(tillSaleReducer, EMPTY_SALE);
  const edit = useCallback(
    (change: Partial<TillSale> | ((current: TillSale) => Partial<TillSale>)) => dispatch({ type: "edit", change }),
    [],
  );
  const {
    cart, customerId, commitmentCustomer, pickId, linkedPickIds, heldNote, notePrinted, noteInternal,
    salesStaffId, quoteId, resumedSale, kitBlocks, creditBlock, creditOverride, creditOverrideReason,
    dueDateEdit, skuId, qty,
  } = sale;
  const [locationId, setLocationId] = useState("");
  const [pendingShowroom, setPendingShowroom] = useState<string | null>(null);
  const [view, setView] = useState(0);
  const [quoteNumbers, setQuoteNumbers] = useState<Record<string, string>>({});
  // A quote fetched from the URL, waiting for an empty, ready cart.
  const [incomingQuote, setIncomingQuote] = useState<Quote | null>(null);
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
  const [tender, setTender] = useState<TillTender>("statement");
  const [amountTendered, setAmountTendered] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [quantityRefusal, setQuantityRefusal] = useState<QuantityRuleRefusal | null>(null);
  const [lastSale, setLastSale] = useState<TillSaleResult | null>(null);
  const [lastBuyerName, setLastBuyerName] = useState(WALK_IN_CUSTOMER_NAME);
  // Remounts the cart editor after a sale so its search and page start over.
  const [soldCount, setSoldCount] = useState(0);
  const [scanValue, setScanValue] = useState("");
  const [scannerOpen, setScannerOpen] = useState(false);
  const [confirmedPicks, setConfirmedPicks] = useState<PickDocument[]>([]);
  const [resumePickId, setResumePickId] = useState("");
  const [resumingPick, setResumingPick] = useState(false);
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
    ...(quoteId ? { quoteId } : {}),
    lines: cart.map((line) => ({
      skuId: line.sku.id, qty: line.qty, discountPercent: line.discountPercent,
    })),
  }), [locationId, customerId, pickId, linkedPickIds, heldNote, notePrinted, noteInternal, salesStaffId, quoteId, cart]);

  const applySnapshot = useCallback((snapshot: TillCartSnapshot, restored: RestoredCart) => {
    dispatch({
      type: "restore",
      snapshot: { ...snapshot, salesStaffId: snapshot.salesStaffId || rememberedColleague() },
      lines: restored.lines,
      customer: restored.customer,
    });
    if (snapshot.locationId) setLocationId(snapshot.locationId);
    setCartReady(true);
  }, []);

  const tillDefaultId = companySettings?.default_till_location_id;
  useEffect(() => {
    if (!allLocations || companySettings === null) return;
    setLocationId((current) => current || resolveTillLocationId(locations, user?.default_location_id, tillDefaultId));
  }, [allLocations, companySettings, locations, tillDefaultId, user]);

  const inventoryBySku = useMemo(
    () => new Map(inventory.map((entry) => [entry.sku_id, entry])),
    [inventory],
  );

  const selectedCustomer =
    customers.find((customer) => customer.id === customerId) ??
    (commitmentCustomer?.id === customerId ? commitmentCustomer : null);

  const skuOptions = skus.filter((sku) => {
    if (sku.is_archived || !sku.is_sellable || !locationId) return false;
    if (sku.till_no_stock_required && !sku.is_kit) {
      return mayBePriced(sku, selectedCustomer, priceLists);
    }
    if (!sku.retail_ex_vat) return false;
    if (sku.is_kit) return true;
    // Any active location: stock not at this showroom is picked against the invoice.
    return (inventoryBySku.get(sku.id)?.locations ?? []).some(
      (loc) => loc.on_hand > 0 && sellableLocationIds.has(loc.location_id),
    );
  });

  const pendingTillPicks = tillPicks.filter(isPendingTillPick);

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
  const reservedReason = (sku: Sku) =>
    requiresTillFloorStock(sku) ? availabilityFor(sku.id).reason : null;

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
          client.setQueryData(stockQueries.tillPicks.queryKey, picks);
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
  }, [cartKitKey, client]);

  // Reads the latest loaded data without restarting a restore when a refetch lands.
  const hydrateLoaded = useEffectEvent((snapshot: TillCartSnapshot) => hydrateCart(snapshot, skus, tillPicks, customers));
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
        const restored = await hydrateLoaded(snapshot);
        if (!cancelled) applySnapshot(snapshot, restored);
      } catch (failure) {
        if (!cancelled) setRestoreBlocked(true);
        throw failure;
      }
    })().catch((failure: unknown) => {
      if (!cancelled) setError(failure instanceof Error ? failure.message : "Could not restore the saved cart.");
    });
    return () => { cancelled = true; };
  }, [applySnapshot, canSell, cartReady, loadSucceeded, locationId, pendingHeld, restoreBlocked, saver]);

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

  const priceRequest = useMemo(() => tillPriceRequest(cart, customerId), [cart, customerId]);
  const pricing = useQuery({
    queryKey: [...PRICE_PREVIEW_KEY, priceRequest],
    queryFn: ({ signal }) => previewTillPrices(priceRequest, signal),
    enabled: canSell && cartReady && priceRequest.lines.length > 0,
    // A preview holds for the request it priced, now: a cart that returns to it is priced again.
    gcTime: 0,
  });
  const pricePreview = pricing.data;
  const pricingError = pricing.error?.message;
  /** Drop the shown preview and price the cart again. */
  const refreshPrices = () => void client.resetQueries({ queryKey: PRICE_PREVIEW_KEY });

  const totalInc = Number(pricePreview?.total_inc_vat ?? 0);
  const totalIncLabel = pricePreview || !cart.length ? formatPriceAmount(totalInc) : "";

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
  const creditOverrideActive = isCreditOverrideActive(sale, tender, canOverrideCredit);

  const tenderedAmount = parsePriceInput(amountTendered) ?? totalInc;
  const changeAmount = Math.max(0, tenderedAmount - totalInc);
  const showChange = Boolean(pricePreview) && (tender === "cash" || tender === "eft");

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
        hasServicePrice: (sku) => mayBePriced(sku, selectedCustomer, priceLists),
      });
      if (!result.ok) {
        const scanned = skus.find((sku) => sku.our_barcode === trimmed) ??
          (allowOurRef ? skus.find((sku) => sku.our_ref === trimmed) : undefined);
        if (scanned && showReserved(scanned)) return false;
        setError(tillScanErrorMessage(result.error));
        return false;
      }
      setError(null);
      edit((current) => ({ cart: mergeCartBySku(current.cart, result.sku, result.qty) }));
      setScanValue("");
      focusScanField();
      return true;
    },
    [availabilityFor, canSell, cartQtyBySku, cartReady, edit, focusScanField, heldLocked, locationId, priceLists, selectedCustomer, showReserved, skus, view],
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

  const unavailableStock = resumedSale || quoteId ? cart.filter((line) =>
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
    !anyLineBlocked(pricePreview) &&
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
      !mayBePriced(sku, selectedCustomer, priceLists)
    )
      return false;
    const needsFloorStock = requiresTillFloorStock(sku);
    const { limit, addable } = availabilityFor(sku.id);
    if (needsFloorStock && quantity > addable) {
      if (!showReserved(sku)) setError(tillScanErrorMessage("over_floor"));
      return false;
    }
    setError(null);
    edit(({ cart: current }) => {
      const reserved = current
        .filter((line) => line.sku.id === sku.id)
        .reduce((sum, line) => sum + line.qty, 0);
      if (needsFloorStock && quantity > limit - reserved)
        return {};
      return { cart: mergeCartBySku(current, sku, quantity) };
    });
    if (!sku.is_kit) focusScanField();
    return true;
  }

  function updateCartLine(
    key: string,
    patch: Partial<Pick<CartLine, "qty" | "discountPercent">>,
  ) {
    edit(({ cart: current }) => ({
      cart: current.map((line) => {
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
    }));
  }

  function removeCartLine(key: string) {
    const skuId = cart.find((line) => line.key === key)?.sku.id;
    if (!skuId) return;
    edit((current) => ({
      cart: current.cart.filter((line) => line.key !== key),
      linkedPickIds: Object.fromEntries(
        Object.entries(current.linkedPickIds).filter(([id]) => id !== skuId),
      ),
    }));
    if (linkedPickIds[skuId] === pickId ||
        tillPicks.some((pick) => pick.id === pickId && pick.kit_sku_id === skuId)) {
      edit({ pickId: "" });
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
      edit((current) => ({
        commitmentCustomer: customer,
        customerId: nextCustomerId,
        cart: [...current.cart, { key: sku.id, sku, qty: pick.kit_qty ?? 0, discountPercent: 0 }],
        linkedPickIds: { ...current.linkedPickIds, [sku.id]: pick.id },
        pickId: pick.id,
      }));
      setResumePickId("");
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Could not resume this pick.",
      );
    } finally {
      setResumingPick(false);
    }
  }

  useEffect(() => {
    if (!quoteParam || !canSell) return;
    // ponytail: no cancel flag; the URL param is dropped only once the quote is loaded or declined.
    getQuote(quoteParam)
      .then((quote) => {
        if (quote.status === "converted" || quote.status === "accepted" || quote.status === "cancelled") {
          throw new Error(`${quote.quote_number} is ${quote.status} and cannot be sold again.`);
        }
        setIncomingQuote(quote);
      })
      .catch((failure: unknown) => {
        setError(failure instanceof Error ? failure.message : "Could not load the quote.");
        router.replace("/till");
      });
  }, [canSell, quoteParam, router]);

  useEffect(() => {
    if (!quoteId || quoteNumbers[quoteId]) return;
    let live = true;
    getQuote(quoteId)
      .then((quote) => { if (live) setQuoteNumbers((current) => ({ ...current, [quote.id]: quote.quote_number })); })
      .catch(() => undefined);
    return () => { live = false; };
  }, [quoteId, quoteNumbers]);

  /** Put an open quote's customer, lines, notes and colleague into the empty cart. */
  const loadQuote = useCallback(async (quote: Quote) => {
    setIncomingQuote(null);
    router.replace("/till");
    try {
      const missing: string[] = [];
      const lines: CartLine[] = [];
      for (const line of quote.lines) {
        const sku = skus.find((item) => item.id === line.sku_id) ?? await getSku(line.sku_id).catch(() => null);
        if (!sku || sku.is_archived || !sku.is_sellable) {
          missing.push(line.our_ref);
          continue;
        }
        lines.push({ key: sku.id, sku, qty: line.qty, discountPercent: Number(line.discount_percent) });
      }
      const customer = customers.find((item) => item.id === quote.customer_id) ?? await getCustomer(quote.customer_id);
      if (customer.is_archived) throw new Error(`${customer.name} is archived. Restore the customer to sell this quote.`);
      const walkIn = customer.name === WALK_IN_CUSTOMER_NAME;
      edit({
        commitmentCustomer: walkIn ? null : customer,
        customerId: walkIn ? "" : customer.id,
        cart: lines,
        notePrinted: quote.notes ?? "",
        noteInternal: quote.internal_note ?? "",
        ...(quote.sales_staff_id && colleagues?.some((item) => item.id === quote.sales_staff_id)
          ? { salesStaffId: quote.sales_staff_id }
          : {}),
        quoteId: quote.id,
      });
      setQuoteNumbers((current) => ({ ...current, [quote.id]: quote.quote_number }));
      setLastSale(null);
      setView(0);
      setError(missing.length
        ? `${missing.join(", ")} could not be added: the product is archived or not for sale.`
        : null);
      setHeldNotice({ title: `${quote.quote_number} is in the till`, subtitle: "Check the payment method, prices and available stock before completing the sale." });
    } catch (failure: unknown) {
      setError(failure instanceof Error ? failure.message : "Could not load the quote.");
    }
  }, [colleagues, customers, edit, router, skus]);

  useEffect(() => {
    // Waits for the colleague list so the quote's colleague carries over.
    if (incomingQuote && cartReady && !heldLocked && !submitting && cart.length === 0 &&
        (colleagues !== null || colleaguesError)) {
      void loadQuote(incomingQuote);
    }
  }, [cart.length, cartReady, colleagues, colleaguesError, heldLocked, incomingQuote, loadQuote, submitting]);

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
    dispatch({ type: "reset" });
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
        dispatch({ type: "reset" });
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
        client.setQueryData(queryKeys.skus, next.latestSkus);
        client.setQueryData(stockQueries.tillPicks.queryKey, next.latestPicks);
        client.setQueryData(queryKeys.inventory, next.latestInventory);
        saver.reset(result.basket);
        setExpiresAt(result.basket.expires_at ?? null);
        refreshReservations();
        dispatch({ type: "reset" });
        applySnapshot(snapshot, restored);
        edit({ resumedSale: true });
        setTender("statement");
        // A resumed cart equal to the current one keeps its query key: price it again anyway.
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
    edit({ creditBlock: null, kitBlocks: [] });
    setLastSale(null);
    try {
      const outcome = await completeTillSale({ flush: () => saver.flush(), create: createTillSale }, sale, {
        locationId,
        tender,
        dueDate,
        priceRevision: pricePreview.price_revision,
        salesStaffId: colleague?.id,
        canOverrideCredit,
      });
      switch (outcome.kind) {
        case "sold":
          setLastBuyerName(selectedCustomer?.name ?? WALK_IN_CUSTOMER_NAME);
          setLastSale(outcome.result);
          dispatch({ type: "reset" });
          setSoldCount((count) => count + 1);
          setHeldNotice(null);
          setBasketNotice(null);
          // The server emptied the basket with the sale.
          reloadBasket();
          refreshReservations();
          focusScanField();
          try {
            // What a sale changes: stock, picks, the buyer's balance; SKUs as the full reload did.
            await Promise.all([queryKeys.inventory, queryKeys.picks, queryKeys.customers, queryKeys.skus]
              .map((queryKey) => client.invalidateQueries({ queryKey }, { throwOnError: true })));
          } catch (failure) {
            setError(failure instanceof Error ? failure.message : "Could not refresh the till after the sale.");
          }
          return;
        case "basket_conflict":
          // Expired, reserved elsewhere or changed: show the server basket and say why.
          reloadBasket(outcome.error);
          return;
        case "kit_requires_pick":
          edit({ kitBlocks: outcome.kits });
          return;
        case "price_conflict":
          setError(outcome.message);
          refreshPrices();
          return;
        case "credit_block":
          setError(outcome.message);
          edit({ creditBlock: outcome.message });
          return;
        case "quantity_rule":
          setError(outcome.message);
          setQuantityRefusal(outcome.refusal);
          return;
        case "error":
          setError(outcome.message);
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
    edit({ pickId: next.pickId, linkedPickIds: next.linkedPickIds, kitBlocks: next.blocks });
    client.setQueryData(stockQueries.tillPicks.queryKey, (current: PickDocument[] = []) => [
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
    edit({ resumedSale: false });
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

      {error || loadError ? (
        <InlineNotification
          kind="error"
          title="Error"
          subtitle={error ?? loadError?.message}
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
      <Modal open={incomingQuote !== null && cartReady && cart.length > 0}
        modalHeading="The till already has a sale" modalLabel={incomingQuote?.quote_number}
        primaryButtonText={heldBusy ? "Holding…" : "Hold it and load quote"} primaryButtonDisabled={heldLocked}
        secondaryButtonText="Cancel" preventCloseOnClickOutside
        onRequestClose={() => {
          if (heldBusy) return;
          setIncomingQuote(null);
          router.replace("/till");
        }}
        onRequestSubmit={() => void startHeldOperation()}>
        <p>
          The current sale has {cart.length} product {cart.length === 1 ? "line" : "lines"}. Loading
          the quote puts that sale on hold so you can resume it later.
        </p>
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
      {quoteId && <div>
        <InlineNotification kind="info" lowContrast hideCloseButton
          title={`Loaded from ${quoteNumbers[quoteId] ?? "a quote"}.`}
          subtitle="Completing this sale marks the quote Converted and links it to the new invoice." />
        <Button kind="ghost" size="sm" href={`/quotes/${quoteId}`}>Open quote</Button>
        <Button kind="ghost" size="sm" onClick={() => edit({ quoteId: "" })}>Unlink quote</Button>
      </div>}
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
        <CartEditor
          key={soldCount}
          mode="till"
          products={skuOptions}
          cart={cart}
          onAdd={addKnownProduct}
          onUpdateLine={updateCartLine}
          onRemoveLine={removeCartLine}
          skuId={skuId}
          onSkuIdChange={(id) => edit({ skuId: id })}
          qty={qty}
          onQtyChange={(value) => edit({ qty: value })}
          customers={
            commitmentCustomer?.id === customerId &&
            !customers.some((item) => item.id === customerId)
              ? [...customers, commitmentCustomer]
              : customers
          }
          customerId={customerId}
          onCustomerChange={(id) => edit({ customerId: id })}
          selectedCustomer={selectedCustomer}
          onAddCustomer={() => router.push("/customers")}
          onBrowseCatalogue={() => router.push("/catalogue")}
          preview={pricePreview}
          pricingError={pricingError}
          onRetryPricing={refreshPrices}
          canDiscount={canDiscount}
          canBreakBatches={can(user, "sales.price_override")}
          quantityRefusal={quantityRefusal}
          colleagues={colleagues}
          colleaguesError={colleaguesError}
          salesStaffId={salesStaffId}
          onSalesStaffChange={(id) => edit({ salesStaffId: id })}
          notePrinted={notePrinted}
          onNotePrintedChange={(note) => edit({ notePrinted: note })}
          noteInternal={noteInternal}
          onNoteInternalChange={(note) => edit({ noteInternal: note })}
          searchDisabled={!locationId}
          addDisabled={!cartReady || !locationId}
          qtyMax={(sku) => sku.till_no_stock_required ? undefined : availabilityFor(sku.id).addable || undefined}
          lineQtyMax={(sku) => requiresTillFloorStock(sku) ? availabilityFor(sku.id).limit : undefined}
          canAddQty={(sku, quantity) => !requiresTillFloorStock(sku) || quantity <= availabilityFor(sku.id).addable}
          blockedReason={reservedReason}
          stockState={stockState}
          tileDisabled={(sku) => requiresTillFloorStock(sku) && availabilityFor(sku.id).addable <= 0}
          lineNote={(line) => {
            const stockNote = requiresTillFloorStock(line.sku)
              ? basketStockNote(stockFor(line.sku.id))
              : null;
            return stockNote && (
              <p className={`cds--type-helper-text-01 ${styles.reserved} ${styles.stockState}`}>
                <LocationIcon size={16} aria-hidden />
                {stockNote}
              </p>
            );
          }}
          finderTop={<>
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
          </>}
          finderBottom={<>
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
          </>}
          cartNotice={saleExpiry && (
            <InlineNotification kind={saleExpiry.kind} lowContrast hideCloseButton
              title={saleExpiry.title} subtitle={saleExpiry.subtitle} />
          )}
          afterLines={cart.some((line) => requiresTillFloorStock(line.sku)) && (
            <p className={`cds--type-helper-text-01 ${styles.stockState}`}>
              Stock notes are for staff only and are not printed on the invoice.
            </p>
          )}
        >
                {confirmedPicks.length > 0 ? (
                  <Select
                    id="till-pick"
                    labelText="Existing till pick"
                    value={pickId}
                    onChange={(event) => edit({ pickId: event.target.value })}
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
                      onChange={() => edit((current) => ({ creditOverride: !current.creditOverride }))}
                    />
                    {creditOverride ? (
                      <TextInput
                        id="till-credit-override-reason"
                        labelText="Override reason"
                        value={creditOverrideReason}
                        onChange={(event) =>
                          edit({ creditOverrideReason: event.target.value })
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
                        edit({ dueDateEdit: { customerId, value: event.target.value } })
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
        </CartEditor>
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
              {lastSale.quote_number ? <p>{lastSale.quote_number} converted</p> : null}
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
                    <TableHeader>Discount</TableHeader>
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
                          lastSale.prices_include_vat ? line.unit_inc_vat : line.unit_ex_vat,
                        )}
                      </TableCell>
                      <TableCell>{formatDiscount(line.discount_percent)}</TableCell>
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
                VAT ({vatPercentLabel(lastSale.vat_rate)}): {formatZarAmount(lastSale.vat_amount)}
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
