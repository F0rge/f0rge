"use client";

import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Trash2 } from "lucide-react";
import { Button, Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle, Stepper, cn } from "@f0rge/ui";
import { useStorefrontAnalytics } from "@/components/analytics/analytics-provider";
import { PieceImage } from "@/components/piece-image";
import { zarMinorUnits } from "@/lib/analytics/money";
import { formatCustomerPrice } from "@/lib/order-money";
import type { Bag, BagItem } from "@/lib/bag-server";

export const money = (value: number, currency?: string) => formatCustomerPrice(value, currency);
export const promiseDates = (from: string, by: string) => {
  const format = (value: string) => new Intl.DateTimeFormat("en-ZA", { dateStyle: "medium", timeZone: "UTC" }).format(new Date(`${value}T00:00:00Z`));
  return from === by ? format(from) : `${format(from)} – ${format(by)}`;
};
export const itemCount = (bag: Bag | null) => bag?.items.reduce((total, item) => total + item.quantity, 0) ?? 0;
export const isHeld = (bag: Bag | null) => bag?.hold?.status === "active" && Date.parse(bag.hold.expires_at) > Date.now();
export const DELIVERY_NOTE = "Delivery in selected Gauteng areas, or collect from our showroom at Bedford Square, Bedfordview.";
export const DELIVERY_COST = "Confirmed before payment";

export async function bagRequest(method: string, path = "/api/bag", body?: unknown): Promise<Bag> {
  const response = await fetch(path, {
    method, headers: body === undefined ? undefined : { "content-type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body), cache: "no-store",
  });
  const result = await response.json();
  if (!response.ok) throw new Error(result.message || "The bag could not be updated");
  return result as Bag;
}

type BagContextValue = {
  bag: Bag | null;
  setBag(bag: Bag): void;
  error: string;
  busy: boolean;
  /** Runs a bag request, keeping the returned bag or the error message. */
  update(method: string, path?: string, body?: unknown): Promise<Bag | null>;
  reload(): Promise<void>;
  /** Reserves the bag and opens checkout; a bag needing review goes to /bag. */
  beginCheckout(): Promise<void>;
  open: boolean;
  setOpen(open: boolean): void;
};

const BagContext = createContext<BagContextValue | null>(null);

export function useBag(): BagContextValue {
  const value = useContext(BagContext);
  if (!value) throw new Error("useBag must be used inside BagProvider");
  return value;
}

export function BagProvider({ children }: { children: ReactNode }) {
  const router = useRouter();
  const [bag, setBag] = useState<Bag | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [open, setOpen] = useState(false);
  const reload = useCallback(async () => {
    setError("");
    try { setBag(await bagRequest("GET")); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Please try again"); }
  }, []);
  useEffect(() => { void reload(); }, [reload]);

  const update = useCallback(async (method: string, path = "/api/bag", body?: unknown) => {
    setBusy(true); setError("");
    try {
      const next = await bagRequest(method, path, body);
      setBag(next);
      return next;
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Please try again");
      return null;
    } finally { setBusy(false); }
  }, []);

  const beginCheckout = useCallback(async () => {
    const next = await update("POST", "/api/bag/checkout");
    if (!next) return;
    setOpen(false);
    router.push(isHeld(next) ? "/checkout" : "/bag");
  }, [router, update]);

  return <BagContext.Provider value={{ bag, setBag, error, busy, update, reload, beginCheckout, open, setOpen }}>
    {children}
    <BagDrawer />
  </BagContext.Provider>;
}

/** One bag line: photo or named tile, name, price, quantity capped at stock, remove. */
export function BagLine({ item, compact = false }: { item: BagItem; compact?: boolean }) {
  const { bag, busy, update } = useBag();
  const { capture } = useStorefrontAnalytics();
  const held = isHeld(bag);
  const currency = bag?.currency_code;
  return <li className={cn("flex gap-4", compact ? "border-b pb-4 last:border-0" : "overflow-hidden rounded-xl border bg-card")}>
    <div className={cn("relative shrink-0 overflow-hidden bg-muted", compact ? "size-20 rounded-md" : "w-24 sm:w-32")}>
      <PieceImage product={{ title: item.title, thumbnail: item.thumbnail }} className="min-h-0" />
    </div>
    <div className={cn("min-w-0 flex-1", !compact && "py-4 pr-4")}>
      <div className="flex justify-between gap-2">
        <div className="min-w-0">
          <h3 className={cn("font-medium", compact && "text-sm")}>{item.title}</h3>
          <p className="text-xs text-muted-foreground">{money(item.unit_price, currency)} each</p>
          {item.fulfillment_promise?.kind === "made_to_order" && <p className="text-xs text-muted-foreground" data-testid="line-fulfillment-promise">Made to order · estimated ready {promiseDates(item.fulfillment_promise.estimated_from, item.fulfillment_promise.estimated_by)}</p>}
          {item.fulfillment_promise?.kind === "stocked" && held && <p className="text-xs text-muted-foreground">In stock and reserved</p>}
        </div>
        {!held && <Button type="button" variant="ghost" size="icon" className="-mt-1 shrink-0" aria-label={`Remove ${item.title}`} onClick={() => {
          if (busy) return;
          const valueMinor = zarMinorUnits(item.total);
          if (valueMinor !== null) capture({ name: "storefront_cart_item_removed", properties: { variant_id: item.variant_id, quantity: item.quantity, value_minor: valueMinor, ...(bag?.id ? { cart_id: bag.id } : {}) } });
          void update("DELETE", `/api/bag?item_id=${encodeURIComponent(item.id)}`);
        }}><Trash2 className="size-4" /></Button>}
      </div>
      <div className="mt-2 flex items-center justify-between gap-2">
        {held
          ? <p className="text-sm text-muted-foreground" aria-label={`Quantity of ${item.title}: ${item.quantity}`}>Qty {item.quantity}</p>
          : <Stepper size="compact" label={`Quantity of ${item.title}`} value={item.quantity} min={1} max={item.max_quantity ?? item.quantity} onChange={(quantity) => {
            if (!busy) void update("PATCH", "/api/bag", { item_id: item.id, quantity });
          }} />}
        <p className={cn("font-medium whitespace-nowrap", compact && "text-sm")}>{money(item.total, currency)}</p>
      </div>
    </div>
  </li>;
}

export function BagTotals({ bag, delivery = DELIVERY_COST }: { bag: Bag; delivery?: string }) {
  return <dl className="space-y-2 text-sm">
    <div className="flex justify-between gap-4"><dt>Subtotal</dt><dd data-testid="bag-subtotal">{money(bag.subtotal, bag.currency_code)}</dd></div>
    <div className="flex justify-between gap-4"><dt>Delivery</dt><dd className="text-right">{delivery}</dd></div>
    <div className="flex justify-between gap-4 border-t pt-2 text-base font-medium"><dt>Total</dt><dd data-testid="bag-total">{money(bag.total, bag.currency_code)}</dd></div>
  </dl>;
}

function BagDrawer() {
  const { bag, error, busy, open, setOpen, beginCheckout } = useBag();
  const count = itemCount(bag);
  const held = isHeld(bag);
  return <Sheet open={open} onOpenChange={setOpen}>
    <SheetContent side="right" className="w-full gap-0 sm:max-w-md">
      <SheetHeader className="border-b">
        <SheetTitle>Your bag</SheetTitle>
        <SheetDescription>{count} {count === 1 ? "item" : "items"}</SheetDescription>
      </SheetHeader>
      <p className="bg-muted/50 px-4 py-3 text-sm">{DELIVERY_NOTE}</p>
      <div className="flex-1 overflow-y-auto p-4">
        {error && <p role="alert" className="mb-4 rounded-lg border border-destructive p-3 text-sm text-destructive">{error}</p>}
        {bag && bag.items.length === 0 && <p className="text-sm text-muted-foreground">Your bag is empty.</p>}
        {bag && bag.items.length > 0 && <ul className="space-y-4">{bag.items.map((item) => <BagLine key={item.id} item={item} compact />)}</ul>}
      </div>
      {bag && bag.items.length > 0 && <div className="space-y-4 border-t p-4">
        <BagTotals bag={bag} />
        <p className="text-xs text-muted-foreground">Plus delivery, if you choose it. VAT included.</p>
        {/* Mantine's unlayered button reset makes buttons inherit their font, so the wrapper carries it. */}
        <div className="grid gap-2 text-sm font-medium">
          {held
            ? <Button className="h-11 w-full" nativeButton={false} role="link" render={<Link href="/checkout" onClick={() => setOpen(false)} />}>Continue checkout</Button>
            : <Button className="h-11 w-full" disabled={busy} onClick={() => void beginCheckout()}>Checkout</Button>}
          <Button variant="outline" className="h-11 w-full" nativeButton={false} role="link" render={<Link href="/bag" onClick={() => setOpen(false)} />}>View bag</Button>
        </div>
      </div>}
    </SheetContent>
  </Sheet>;
}
