"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import type { Bag } from "@/lib/bag-server";

const money = (value: number) => new Intl.NumberFormat("en-ZA", { style: "currency", currency: "ZAR" }).format(value);
const promiseDates = (from: string, by: string) => {
  const format = (value: string) => new Intl.DateTimeFormat("en-ZA", { dateStyle: "medium", timeZone: "UTC" }).format(new Date(`${value}T00:00:00Z`));
  return from === by ? format(from) : `${format(from)} – ${format(by)}`;
};

async function bagRequest(method: string, path = "/api/bag", body?: unknown): Promise<Bag> {
  const response = await fetch(path, {
    method, headers: body === undefined ? undefined : { "content-type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body), cache: "no-store",
  });
  const result = await response.json();
  if (!response.ok) throw new Error(result.message || "The bag could not be updated");
  return result as Bag;
}

export default function BagPage() {
  const router = useRouter();
  const [bag, setBag] = useState<Bag | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const loadBag = useCallback(async () => {
    setError("");
    try { setBag(await bagRequest("GET")); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Please try again"); }
  }, []);
  useEffect(() => { void loadBag(); }, [loadBag]);

  async function update(method: string, path: string, body?: unknown) {
    setBusy(true); setError("");
    try { setBag(await bagRequest(method, path, body)); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Please try again"); }
    finally { setBusy(false); }
  }

  async function beginCheckout() {
    setBusy(true); setError("");
    try {
      const nextBag = await bagRequest("POST", "/api/bag/checkout");
      setBag(nextBag);
      if (nextBag.hold?.status === "active") router.push("/checkout");
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Please try again"); }
    finally { setBusy(false); }
  }

  const held = bag?.hold?.status === "active" && Date.parse(bag.hold.expires_at) > Date.now();
  return <div className="content bag-page">
    <p className="eyebrow">The Collector / your selection</p>
    <h1>Your bag</h1>
    {error && <p role="alert" className="bag-error">{error}</p>}
    {!bag && error && <button type="button" className="bag-retry" onClick={() => void loadBag()}>Retry loading bag</button>}
    {!bag && !error && <p role="status">Loading your bag…</p>}
    {bag && bag.items.length === 0 && <div className="bag-empty"><p>Your bag is empty.</p><Link className="text-link" href="/shop">Explore all pieces ↗</Link></div>}
    {bag && bag.items.length > 0 && <div className="bag-layout">
      <div className="bag-lines">{bag.items.map((item) => <div className="bag-line" key={item.id}>
        <div className="bag-line-image">{item.thumbnail && <img src={item.thumbnail} alt="" />}</div>
        <div><h2>{item.title}</h2><p>{money(item.unit_price)} each</p>
          {item.fulfillment_promise?.kind === "made_to_order" && <p className="line-fulfillment-promise" data-testid="line-fulfillment-promise">Made to order · estimated ready {promiseDates(item.fulfillment_promise.estimated_from, item.fulfillment_promise.estimated_by)}</p>}
          {item.fulfillment_promise?.kind === "stocked" && <p className="line-fulfillment-promise">In stock and reserved</p>}
          <label htmlFor={`quantity-${item.id}`}>Quantity for {item.title}</label>
          <input id={`quantity-${item.id}`} type="number" min="1" max="99" step="1" defaultValue={item.quantity} key={`${item.id}-${item.quantity}`} disabled={busy || held} onBlur={(event) => {
            const quantity = Number(event.target.value);
            if (quantity !== item.quantity) void update("PATCH", "/api/bag", { item_id: item.id, quantity });
          }} />
          <button type="button" className="bag-remove" disabled={busy || held} onClick={() => void update("DELETE", `/api/bag?item_id=${encodeURIComponent(item.id)}`)}>Remove</button>
        </div><strong>{money(item.total)}</strong>
      </div>)}</div>
      <aside className="bag-summary"><p className="eyebrow">Order summary</p><dl><dt>Subtotal</dt><dd>{money(bag.subtotal)}</dd><dt>Total incl. VAT</dt><dd data-testid="bag-total">{money(bag.total)}</dd></dl>
        {bag.hold?.status === "review" && <div className="bag-review" role="status"><h2>Review changes</h2><p>Price or availability changed. Review your bag before continuing.</p>{bag.hold.changes?.map((change) => <p key={change}>{change}</p>)}</div>}
        {bag.hold?.fulfillment_promise && <div className="bag-fulfillment-promise" role="status" data-testid="fulfillment-promise-summary">
          <h2>One fulfillment promise for the whole order</h2>
          <p>{bag.hold.fulfillment_promise.kind === "mixed" ? "Your stocked and made-to-order pieces will be fulfilled together." : bag.hold.fulfillment_promise.kind === "made_to_order" ? "Your order is made to order." : "Your pieces are in stock."}</p>
          <p>Estimated ready {promiseDates(bag.hold.fulfillment_promise.estimated_from, bag.hold.fulfillment_promise.estimated_by)}.</p>
        </div>}
        {held ? <><p role="status">Reserved until {new Date(bag.hold!.expires_at).toLocaleTimeString("en-ZA")}</p><Link className="bag-checkout" href="/checkout">Continue checkout</Link><button type="button" disabled={busy} onClick={() => void update("DELETE", "/api/bag/checkout")}>Change bag</button><button type="button" disabled={busy} onClick={() => void update("DELETE", "/api/bag/checkout")}>Cancel reservation</button></>
          : <button type="button" className="bag-checkout" disabled={busy} onClick={() => void beginCheckout()}>{bag.hold?.status === "review" ? "Accept changes and continue" : "Continue to checkout"}</button>}
        <p className="bag-note">Availability is confirmed when you continue to checkout. No payment is taken here.</p>
      </aside>
    </div>}
  </div>;
}
