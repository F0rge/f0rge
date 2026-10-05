"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { Checkbox, Select } from "@f0rge/ui/forms";
import { useRouter } from "next/navigation";
import { useStorefrontAnalytics } from "@/components/analytics/analytics-provider";
import { zarMinorUnits } from "@/lib/analytics/money";
import { purchaseFeedback } from "@/lib/purchase-feedback";
import type { Bag } from "@/lib/bag-server";

type Fulfillment = "delivery" | "collection";
type PreparedCheckout = {
  session_id: string; status: string; amount: number; currency_code: string; fulfillment_type: Fulfillment;
  provider_id?: string; redirect_url?: string | null;
};
type SavedAddress = { id: string; first_name?: string; last_name?: string; address_1?: string; address_2?: string; city?: string; province?: string; postal_code?: string; phone?: string };
const money = (value: number, currency = "ZAR") => new Intl.NumberFormat("en-ZA", { style: "currency", currency }).format(value);
const promiseDates = (from: string, by: string) => {
  const format = (value: string) => new Intl.DateTimeFormat("en-ZA", { dateStyle: "medium", timeZone: "UTC" }).format(new Date(`${value}T00:00:00Z`));
  return from === by ? format(from) : `${format(from)} – ${format(by)}`;
};

export default function CheckoutPage() {
  const router = useRouter();
  const { capture, attributionHeaders, setSensitiveOverlay } = useStorefrontAnalytics();
  const startedCart = useRef("");
  const [bag, setBag] = useState<Bag | null>(null);
  const [fulfillment, setFulfillment] = useState<Fulfillment>("delivery");
  const [checkout, setCheckout] = useState<PreparedCheckout | null>(null);
  const [paymentStatus, setPaymentStatus] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const errorRef = useRef<HTMLParagraphElement>(null);
  const [savedAddresses, setSavedAddresses] = useState<SavedAddress[]>([]);
  const [accountAvailable, setAccountAvailable] = useState(false);
  const [saveAddress, setSaveAddress] = useState(false);
  const formRef = useRef<HTMLFormElement>(null);

  useEffect(() => {
    void (async () => {
      try {
        const session = await fetch("/api/account/session", { method: "POST", cache: "no-store" });
        if (session.ok) {
          setAccountAvailable(true);
          const addressResponse = await fetch("/api/account/addresses", { cache: "no-store" });
          if (addressResponse.ok) {
            const payload = await addressResponse.json() as { addresses?: SavedAddress[] };
            setSavedAddresses(payload.addresses || []);
          }
        }
        const response = await fetch("/api/bag", { cache: "no-store" });
        if (!response.ok) throw new Error("Your bag could not be loaded");
        setBag(await response.json() as Bag);
      } catch (reason) { setError(reason instanceof Error ? reason.message : "Your bag could not be loaded"); }
    })();
  }, []);

  useEffect(() => {
    setSensitiveOverlay(Boolean(checkout));
    return () => setSensitiveOverlay(false);
  }, [checkout, setSensitiveOverlay]);

  useEffect(() => {
    if (!bag?.id || !bag.items.length || startedCart.current === bag.id) return;
    const valueMinor = zarMinorUnits(bag.total);
    if (valueMinor === null) return;
    startedCart.current = bag.id;
    const checkoutType = accountAvailable ? "account" : "guest";
    capture({ name: "storefront_checkout_started", properties: { cart_id: bag.id, item_count: bag.items.length, value_minor: valueMinor, checkout_type: checkoutType } });
  }, [accountAvailable, bag, capture]);
  useEffect(() => { if (error) errorRef.current?.focus(); }, [error]);

  function fillSavedAddress(id: string) {
    const address = savedAddresses.find((candidate) => candidate.id === id);
    if (!address || !formRef.current) return;
    for (const field of ["first_name", "last_name", "address_1", "address_2", "city", "province", "postal_code", "phone"] as const) {
      const input = formRef.current.elements.namedItem(field) as HTMLInputElement | null;
      if (input) input.value = address[field] || (field === "province" ? "Gauteng" : "");
    }
  }

  async function prepare(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true); setError("");
    const values = Object.fromEntries(new FormData(event.currentTarget).entries());
    try {
      if (saveAddress && accountAvailable && fulfillment === "delivery") {
        const addressResponse = await fetch("/api/account/addresses", {
          method: "POST", headers: { "content-type": "application/json" }, cache: "no-store",
          body: JSON.stringify({
            first_name: values.first_name, last_name: values.last_name,
            address_1: values.address_1, address_2: values.address_2,
            city: values.city, province: values.province,
            postal_code: values.postal_code, phone: values.phone,
          }),
        });
        if (!addressResponse.ok) throw new Error("The address could not be saved. Review it or continue without saving.");
      }
      const response = await fetch("/api/checkout/prepare", {
        method: "POST", headers: { "content-type": "application/json" }, cache: "no-store", body: JSON.stringify({ ...values, fulfillment_type: fulfillment }),
      });
      const payload = await response.json() as { checkout?: PreparedCheckout; message?: string };
      if (!response.ok || !payload.checkout) throw new Error(payload.message || "Checkout could not be prepared");
      if (bag?.id) {
        const checkoutType = accountAvailable ? "account" : "guest";
        capture({ name: "storefront_shipping_method_selected", properties: { cart_id: bag.id, method_id: fulfillment } });
        capture({ name: "storefront_checkout_step_completed", properties: { cart_id: bag.id, step: "fulfillment", checkout_type: checkoutType } });
      }
      if (payload.checkout.provider_id === "pp_peach_sandbox" && payload.checkout.redirect_url) {
        const redirect = new URL(payload.checkout.redirect_url);
        if (redirect.origin !== "https://testsecure.peachpayments.com") throw new Error("The hosted payment destination could not be verified");
        setSensitiveOverlay(true);
        window.location.assign(redirect.toString());
        return;
      }
      setCheckout(payload.checkout);
      setPaymentStatus(payload.checkout.status === "initiation_unknown" ? "unknown" : payload.checkout.status);
    } catch (reason) {
      capture({ name: "storefront_friction_noted", properties: { surface: "checkout", kind: "checkout_unavailable" } });
      setError(reason instanceof Error ? reason.message : "Checkout could not be prepared");
    }
    finally { setBusy(false); }
  }

  async function simulate(outcome: "success" | "pending" | "declined" | "cancelled" | "unknown", eventId = crypto.randomUUID()) {
    if (!checkout) return;
    setBusy(true); setError("");
    try {
      const response = await fetch("/api/checkout/payment", {
        method: "POST", headers: { "content-type": "application/json", ...attributionHeaders() }, cache: "no-store",
        body: JSON.stringify({ session_id: checkout.session_id, outcome, event_id: eventId }),
      });
      const payload = await response.json() as { payment?: { status?: string }; message?: string };
      if (!response.ok) throw new Error(payload.message || "Payment status is unknown");
      const status = payload.payment?.status || "unknown";
      setPaymentStatus(status);
      if (status === "captured") router.push("/order/confirmation");
      if (status === "declined" || status === "cancelled" || status === "unknown") {
        capture({ name: "storefront_friction_noted", properties: { surface: "payment", kind: status === "declined" ? "payment_declined" : status === "cancelled" ? "payment_cancelled" : "payment_unknown" } });
      }
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
  const feedback = error ? purchaseFeedback(error, true) : null;
  const total = checkout ? Number(checkout.amount) : bag?.total || 0;
  return <div className="content checkout-page" data-storefront-no-capture="">
    <p className="eyebrow">The Collector / secure checkout</p>
    <h1>Review your order</h1>
    <p className="checkout-intro">Confirm your contact and fulfillment details. The server checks availability and calculates the final VAT-inclusive ZAR total before payment.</p>
    <div className="checkout-layout">
      <section className="checkout-main">
        {!bag && !error && <p role="status">Loading your bag…</p>}
        {bag && bag.items.length === 0 && <p>Your bag is empty. <Link href="/shop" className="text-link">Explore all pieces ↗</Link></p>}
        {feedback && <p ref={errorRef} id="checkout-error" role={feedback.role} tabIndex={feedback.tabIndex} className="bag-error">{feedback.message}</p>}
        {checkout ? <div className="checkout-payment" data-testid={checkout.provider_id === "pp_peach_sandbox" ? "peach-payment-panel" : "test-payment-panel"}>
          <p className="eyebrow">{checkout.provider_id === "pp_peach_sandbox" ? "Secure hosted payment" : "Test payment only"}</p>
          <h2>{money(total, checkout.currency_code.toUpperCase())}</h2>
          <p>{checkout.provider_id === "pp_peach_sandbox"
            ? "Continue on Peach Payments secure checkout. The payment result will be confirmed by a signed server notification."
            : "No real payment is taken. Choose an outcome to exercise the local simulator."} Your confirmation access was saved before this payment session was returned.</p>
          <p role="status" data-testid="payment-status">Payment status: {paymentStatus || "pending"}</p>
          {paymentStatus === "declined" && <p role="alert">{checkout.provider_id === "pp_peach_sandbox"
            ? "Peach declined this payment. Do not reuse this checkout session; contact the store before trying another payment."
            : "The test payment was declined. Your bag and reservation remain available until the hold expires."}</p>}
          {paymentStatus === "cancelled" && <p role="status">{checkout.provider_id === "pp_peach_sandbox"
            ? "The Peach checkout was cancelled. Contact the store before starting another payment for this bag."
            : "The test payment was cancelled. You can retry while the reservation is active."}</p>}
          {paymentStatus === "pending" && <p role="status">The payment is pending. You can close this page and return to the private order confirmation later.</p>}
          {paymentStatus === "unknown" && <p role="alert">{checkout.provider_id === "pp_peach_sandbox"
            ? "Peach has not confirmed this payment yet. Do not pay again; wait for the status check or contact the store before retrying."
            : "The payment result is unknown. Your private confirmation page can check again without creating a second order."}</p>}
          {paymentStatus === "paid_exception" && <p role="alert">Payment succeeded, but the inventory commitment needs recovery. Keep the private confirmation page for the current status.</p>}
          {checkout.provider_id !== "pp_peach_sandbox" && <div className="test-payment-actions">
            <button type="button" disabled={busy} onClick={() => void simulate("success")}>Simulate success</button>
            <button type="button" disabled={busy} onClick={() => void simulate("pending")}>Simulate pending</button>
            <button type="button" disabled={busy} onClick={() => void simulate("declined")}>Simulate decline</button>
            <button type="button" disabled={busy} onClick={() => void simulate("cancelled")}>Simulate cancellation</button>
            <button type="button" disabled={busy} onClick={() => void simulate("unknown")}>Simulate unknown result</button>
          </div>}
          <Link className="text-link" href="/order/confirmation">Check private order status ↗</Link>
        </div> : <form ref={formRef} className="checkout-form" onSubmit={(event) => void prepare(event)}>
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
            {savedAddresses.length > 0 && <Select label="Use a saved address" defaultValue="" onChange={(value) => fillSavedAddress(value || "")} data={[{ value: "", label: "Enter a new address" }, ...savedAddresses.map((address) => ({ value: address.id, label: `${address.address_1}${address.address_2 ? `, ${address.address_2}` : ""} — ${address.city}` }))]} />}
            <label>Street address<input name="address_1" autoComplete="address-line1" required maxLength={250} /></label>
            <label>Suburb<input name="address_2" autoComplete="address-line2" required maxLength={150} /></label>
            <div className="checkout-fields">
              <label>City<input name="city" autoComplete="address-level2" required maxLength={100} /></label>
              <label>Province<input name="province" autoComplete="address-level1" required maxLength={100} defaultValue="Gauteng" /></label>
            </div>
            <label>Postal code<input name="postal_code" inputMode="numeric" autoComplete="postal-code" pattern="[0-9]{4}" required /></label>
            {accountAvailable && <Checkbox className="save-address-choice" checked={saveAddress} onChange={(event) => setSaveAddress(event.target.checked)} label="Save this address to your account for next time" />}
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
        {bag?.items.map((item) => <div className="checkout-summary-line" key={item.id}><span>{item.title} × {item.quantity}{item.fulfillment_promise?.kind === "made_to_order" && <small>Made to order · {promiseDates(item.fulfillment_promise.estimated_from, item.fulfillment_promise.estimated_by)}</small>}</span><strong>{money(item.total)}</strong></div>)}
        {bag?.hold?.fulfillment_promise && <div className="checkout-fulfillment-promise" role="status" data-testid="checkout-fulfillment-promise">
          <strong>One fulfillment promise for your full order</strong>
          <p>{bag.hold.fulfillment_promise.kind === "mixed" ? "All pieces will be fulfilled together when the made-to-order pieces are ready." : bag.hold.fulfillment_promise.kind === "made_to_order" ? "This order is made to order." : "All pieces are in stock."}</p>
          <p>Estimated ready {promiseDates(bag.hold.fulfillment_promise.estimated_from, bag.hold.fulfillment_promise.estimated_by)}.</p>
        </div>}
        <dl><dt>Bag total incl. VAT</dt><dd>{money(bag?.total || 0)}</dd><dt>Final total incl. VAT</dt><dd data-testid="checkout-total">{money(total)}</dd></dl>
        <p>Prices and delivery are checked by the server. Any change returns you to review before payment.</p>
        <p>Availability is reserved until {bag?.hold?.expires_at ? new Date(bag.hold.expires_at).toLocaleTimeString("en-ZA") : "your hold expires"}.</p>
      </aside>
    </div>
  </div>;
}
