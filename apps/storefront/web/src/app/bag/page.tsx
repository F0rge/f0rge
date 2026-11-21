"use client";

import { useEffect, useRef } from "react";
import Link from "next/link";
import { RotateCcw, Store, Truck, UserRound } from "lucide-react";
import { Button, Card, CardContent, CardDescription, CardHeader, CardTitle } from "@f0rge/ui";
import { BagLine, BagTotals, DELIVERY_NOTE, isHeld, itemCount, promiseDates, useBag } from "@/components/bag";
import { useStorefrontAnalytics } from "@/components/analytics/analytics-provider";
import { zarMinorUnits } from "@/lib/analytics/money";
import { purchaseFeedback } from "@/lib/purchase-feedback";

const assurances = [
  { icon: Truck, title: "Delivery", description: "Selected Gauteng areas. The charge is confirmed before payment." },
  { icon: Store, title: "Collection", description: "From our showroom at Bedford Square, Bedfordview." },
  { icon: RotateCcw, title: "Returns", description: "Change of mind within 30 days of delivery or collection, unused." },
  { icon: UserRound, title: "Guest checkout", description: "No account needed." },
];

export default function BagPage() {
  const { bag, error, busy, update, reload, beginCheckout } = useBag();
  const { capture } = useStorefrontAnalytics();
  const viewedCart = useRef("");
  const errorRef = useRef<HTMLParagraphElement>(null);
  useEffect(() => {
    if (!bag?.id || bag.items.length === 0 || viewedCart.current === bag.id) return;
    const valueMinor = zarMinorUnits(bag.total);
    if (valueMinor === null) return;
    viewedCart.current = bag.id;
    capture({ name: "storefront_cart_viewed", properties: { cart_id: bag.id, item_count: bag.items.length, value_minor: valueMinor } });
  }, [bag, capture]);
  useEffect(() => { if (error) errorRef.current?.focus(); }, [error]);

  const held = isHeld(bag);
  const count = itemCount(bag);
  const feedback = error ? purchaseFeedback(error, true) : null;
  return <div className="mx-auto w-full max-w-7xl px-4 py-10 md:px-6">
    <div className="grid grid-cols-1 gap-8 lg:grid-cols-3">
      <div className="min-w-0 space-y-6 lg:col-span-2">
        <div>
          <h1 className="text-2xl font-semibold">Your bag</h1>
          {bag && <p className="text-muted-foreground">{count} {count === 1 ? "item" : "items"} in your bag</p>}
        </div>
        {feedback && <p ref={errorRef} id="bag-error" role={feedback.role} tabIndex={feedback.tabIndex} className="rounded-lg border border-destructive p-4 text-sm text-destructive outline-none">{feedback.message}</p>}
        {!bag && error && <div className="text-sm font-medium"><Button type="button" variant="outline" onClick={() => void reload()}>Retry loading bag</Button></div>}
        {!bag && !error && <p role="status">Loading your bag…</p>}
        {bag && bag.items.length === 0 && <Card><CardContent className="space-y-4">
          <p className="text-muted-foreground">Your bag is empty.</p>
          <div className="text-sm font-medium"><Button variant="outline" nativeButton={false} role="link" render={<Link href="/shop" />}>Continue shopping</Button></div>
        </CardContent></Card>}
        {bag && bag.items.length > 0 && <ul className="space-y-4">{bag.items.map((item) => <BagLine key={item.id} item={item} />)}</ul>}
      </div>

      {bag && bag.items.length > 0 && <Card className="self-start">
        <CardHeader>
          <CardTitle>Order summary</CardTitle>
          <CardDescription>Prices in rand, VAT included.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="space-y-1">
            <p className="text-sm font-medium">Delivery or collection</p>
            <p className="text-sm text-muted-foreground">{DELIVERY_NOTE}</p>
          </div>
          <div className="space-y-2">
            <BagTotals bag={bag} />
            <p className="text-xs text-muted-foreground">Plus delivery, if you choose it. VAT included.</p>
          </div>
          {bag.hold?.status === "review" && <div className="space-y-1 rounded-lg border border-destructive p-4 text-sm" role="status">
            <h2 className="font-medium">Review changes</h2>
            <p>Price or availability changed. Review your bag before continuing.</p>
            {bag.hold.changes?.map((change) => <p key={change}>{change}</p>)}
          </div>}
          {bag.hold?.fulfillment_promise && <div className="space-y-1 text-sm" role="status" data-testid="fulfillment-promise-summary">
            <h2 className="font-medium">One fulfillment promise for the whole order</h2>
            <p className="text-muted-foreground">{bag.hold.fulfillment_promise.kind === "mixed" ? "Your stocked and made-to-order pieces will be fulfilled together." : bag.hold.fulfillment_promise.kind === "made_to_order" ? "Your order is made to order." : "Your pieces are in stock."}</p>
            <p className="text-muted-foreground">Estimated ready {promiseDates(bag.hold.fulfillment_promise.estimated_from, bag.hold.fulfillment_promise.estimated_by)}.</p>
          </div>}
          {/* Mantine's unlayered button reset makes buttons inherit their font, so the wrapper carries it. */}
          <div className="grid gap-2 text-sm font-medium">
            {held ? <>
              <p role="status" className="font-normal">Reserved until {new Date(bag.hold!.expires_at).toLocaleTimeString("en-ZA")}</p>
              <Button className="h-11 w-full" nativeButton={false} role="link" render={<Link href="/checkout" />}>Continue checkout</Button>
              <Button type="button" variant="outline" className="h-11 w-full" disabled={busy} onClick={() => void update("DELETE", "/api/bag/checkout")}>Change bag</Button>
            </> : <Button type="button" className="h-11 w-full" disabled={busy} onClick={() => void beginCheckout()}>{bag.hold?.status === "review" ? "Accept changes and continue" : "Continue to checkout"}</Button>}
          </div>
          <p className="text-xs text-muted-foreground">Availability is confirmed when you continue to checkout. No payment is taken here.</p>
        </CardContent>
      </Card>}
    </div>

    <ul className="mt-12 grid grid-cols-1 gap-6 border-t pt-8 sm:grid-cols-2 lg:grid-cols-4">{assurances.map(({ icon: Icon, title, description }) => <li key={title} className="flex gap-3">
      <Icon className="mt-0.5 size-5 shrink-0 text-primary" aria-hidden="true" />
      <div><h2 className="text-sm font-medium">{title}</h2><p className="text-sm text-muted-foreground">{description}</p></div>
    </li>)}</ul>
  </div>;
}
