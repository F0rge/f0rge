"use client";

import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import type { Bag } from "@/lib/bag-server";

type Fulfillment = "delivery" | "collection";
type PreparedCheckout = { session_id: string; status: string; amount: number; currency_code: string; fulfillment_type: Fulfillment };
const money = (value: number, currency = "ZAR") => new Intl.NumberFormat("en-ZA", { style: "currency", currency }).format(value);

export default function CheckoutPage() {
  const router = useRouter();
  const [bag, setBag] = useState<Bag | null>(null);
  const [fulfillment, setFulfillment] = useState<Fulfillment>("delivery");
  const [checkout, setCheckout] = useState<PreparedCheckout | null>(null);
  const [paymentStatus, setPaymentStatus] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    void fetch("/api/bag", { cache: "no-store" }).then(async (response) => {
      if (!response.ok) throw new Error("Your bag could not be loaded");
      setBag(await response.json() as Bag);
    }).catch((reason) => setError(reason instanceof Error ? reason.message : "Your bag could not be loaded"));
  }, []);

  async function prepare(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true); setError("");
    const values = Object.fromEntries(new FormData(event.currentTarget).entries());
    try {
      const response = await fetch("/api/checkout/prepare", {
        method: "POST", headers: { "content-type": "application/json" }, cache: "no-store", body: JSON.stringify({ ...values, fulfillment_type: fulfillment }),
      });
      const payload = await response.json() as { checkout?: PreparedCheckout; message?: string };
      if (!response.ok || !payload.checkout) throw new Error(payload.message || "Checkout could not be prepared");
      setCheckout(payload.checkout);
      setPaymentStatus(payload.checkout.status);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Checkout could not be prepared"); }
    finally { setBusy(false); }
  }

  async function simulate(outcome: "success" | "pending" | "declined" | "cancelled" | "unknown", eventId = crypto.randomUUID()) {
    if (!checkout) return;
    setBusy(true); setError("");
    try {
      const response = await fetch("/api/checkout/payment", {
        method: "POST", headers: { "content-type": "application/json" }, cache: "no-store",
        body: JSON.stringify({ session_id: checkout.session_id, outcome, event_id: eventId }),
      });
      const payload = await response.json() as { payment?: { status?: string }; message?: string };
      if (!response.ok) throw new Error(payload.message || "Payment status is unknown");
      const status = payload.payment?.status || "unknown";
      setPaymentStatus(status);
      if (status === "captured") router.push("/order/confirmation");
    } catch (reason) {
      setPaymentStatus("unknown");
      setError(reason instanceof Error ? reason.message : "Payment status is unknown");
    } finally { setBusy(false); }
  }

  async function releaseHold() {
    await fetch("/api/bag/checkout", { method: "DELETE", cache: "no-store" });
    router.push("/bag");
  }

  const held = bag?.hold?.status === "active" && Date.parse(bag.hold.expires_at) > Date.now();
  const total = checkout ? Number(checkout.amount) : bag?.total || 0;
  return <div className="content checkout-page">
    <p className="eyebrow">The Collector / secure checkout</p>
    <h1>Review your order</h1>
    <p className="checkout-intro">Confirm your contact and fulfillment details. The server checks availability and calculates the final VAT-inclusive ZAR total before the test payment begins.</p>
    <div className="checkout-layout">
      <section className="checkout-main">
        {!bag && !error && <p role="status">Loading your bag…</p>}
        {bag && bag.items.length === 0 && <p>Your bag is empty. <Link href="/shop" className="text-link">Explore all pieces ↗</Link></p>}
        {error && <p role="alert" className="bag-error">{error}</p>}
        {checkout ? <div className="checkout-payment" data-testid="test-payment-panel">
          <p className="eyebrow">Test payment only</p>
          <h2>{money(total, checkout.currency_code.toUpperCase())}</h2>
          <p>No real payment is taken. Choose an outcome to exercise the local simulator. Your confirmation access was saved before this payment session was returned.</p>
          <p role="status" data-testid="payment-status">Payment status: {paymentStatus || "pending"}</p>
          {paymentStatus === "declined" && <p role="alert">The test payment was declined. Your bag and reservation remain available until the hold expires.</p>}
          {paymentStatus === "cancelled" && <p role="status">The test payment was cancelled. You can retry while the reservation is active.</p>}
          {paymentStatus === "pending" && <p role="status">The payment is pending. You can close this page and return to the private order confirmation later.</p>}
          {paymentStatus === "unknown" && <p role="alert">The payment result is unknown. Your private confirmation page can check again without creating a second order.</p>}
          {paymentStatus === "paid_exception" && <p role="alert">The test payment succeeded, but the inventory commitment needs recovery. Keep the private confirmation page for the current status.</p>}
          <div className="test-payment-actions">
            <button type="button" disabled={busy} onClick={() => void simulate("success")}>Simulate success</button>
            <button type="button" disabled={busy} onClick={() => void simulate("pending")}>Simulate pending</button>
            <button type="button" disabled={busy} onClick={() => void simulate("declined")}>Simulate decline</button>
            <button type="button" disabled={busy} onClick={() => void simulate("cancelled")}>Simulate cancellation</button>
            <button type="button" disabled={busy} onClick={() => void simulate("unknown")}>Simulate unknown result</button>
          </div>
          <Link className="text-link" href="/order/confirmation">Check private order status ↗</Link>
        </div> : <form className="checkout-form" onSubmit={(event) => void prepare(event)}>
          <h2>Contact</h2>
          <label>Email<input name="email" type="email" autoComplete="email" required maxLength={254} /></label>
          <div className="checkout-fields">
            <label>First name<input name="first_name" autoComplete="given-name" required maxLength={100} /></label>
            <label>Last name<input name="last_name" autoComplete="family-name" required maxLength={100} /></label>
          </div>
          <label>Phone<input name="phone" type="tel" autoComplete="tel" required maxLength={40} /></label>
          <h2>Fulfillment</h2>
          <fieldset className="fulfillment-choice">
            <legend>Choose how to receive your order</legend>
            <label><input type="radio" name="fulfillment_type" checked={fulfillment === "delivery"} onChange={() => setFulfillment("delivery")} /> Gauteng delivery</label>
            <label><input type="radio" name="fulfillment_type" checked={fulfillment === "collection"} onChange={() => setFulfillment("collection")} /> Collection</label>
          </fieldset>
          {fulfillment === "delivery" ? <div className="checkout-address">
            <label>Street address<input name="address_1" autoComplete="address-line1" required maxLength={250} /></label>
            <label>Suburb<input name="address_2" autoComplete="address-line2" required maxLength={150} /></label>
            <div className="checkout-fields">
              <label>City<input name="city" autoComplete="address-level2" required maxLength={100} /></label>
              <label>Province<input name="province" autoComplete="address-level1" required maxLength={100} defaultValue="Gauteng" /></label>
            </div>
            <label>Postal code<input name="postal_code" inputMode="numeric" autoComplete="postal-code" pattern="[0-9]{4}" required /></label>
            <p className="checkout-help">Delivery is limited to server-configured Gauteng zones. Rates are set by the store and shown in your final total.</p>
          </div> : <p className="checkout-help">Collection is free. Collection point details will be provided with your order confirmation.</p>}
          <button className="bag-checkout" type="submit" disabled={busy || !held || !bag?.items.length}>
            {busy ? "Checking order…" : "Review total and continue"}
          </button>
          {!held && <p role="alert">Your reservation expired. Return to your bag to review and reserve the pieces again.</p>}
          <button className="checkout-back" type="button" disabled={busy} onClick={() => void releaseHold()}>Change bag</button>
        </form>}
      </section>
      <aside className="checkout-summary">
        <p className="eyebrow">Order summary</p>
        {bag?.items.map((item) => <div className="checkout-summary-line" key={item.id}><span>{item.title} × {item.quantity}</span><strong>{money(item.total)}</strong></div>)}
        <dl><dt>Bag total incl. VAT</dt><dd>{money(bag?.total || 0)}</dd><dt>Final total incl. VAT</dt><dd data-testid="checkout-total">{money(total)}</dd></dl>
        <p>Prices and delivery are checked by the server. Any change returns you to review before payment.</p>
        <p>Availability is reserved until {bag?.hold?.expires_at ? new Date(bag.hold.expires_at).toLocaleTimeString("en-ZA") : "your hold expires"}.</p>
      </aside>
    </div>
  </div>;
}
