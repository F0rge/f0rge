"use client";

import { FormEvent, useEffect, useRef, useState, type ComponentProps } from "react";
import Link from "next/link";
import { Button, Card, CardContent, CardDescription, CardHeader, CardTitle, Input, Label } from "@f0rge/ui";
import { Checkbox, Select } from "@f0rge/ui/forms";
import { useRouter } from "next/navigation";
import { BagTotals, DELIVERY_COST, isHeld, money, promiseDates, useBag } from "@/components/bag";
import { PieceImage } from "@/components/piece-image";
import { useStorefrontAnalytics } from "@/components/analytics/analytics-provider";
import { zarMinorUnits } from "@/lib/analytics/money";
import { purchaseFeedback } from "@/lib/purchase-feedback";
import { SHOWROOM } from "@/lib/showroom";

type Fulfillment = "delivery" | "collection";
type PreparedCheckout = {
  session_id: string; status: string; amount: number; currency_code: string; fulfillment_type: Fulfillment;
  provider_id?: string; redirect_url?: string | null;
};
type SavedAddress = { id: string; first_name?: string; last_name?: string; address_1?: string; address_2?: string; city?: string; province?: string; postal_code?: string; phone?: string };
// Commerce answers this code (404) when neither Paystack nor the local test provider is configured. It checks
// the provider before anything else, so no order or payment session exists when it does.
const CARD_PAYMENT_UNAVAILABLE = "payment_unavailable";
const methods = [
  { id: "delivery", label: "Delivery", description: "Selected Gauteng areas. The delivery charge is confirmed in your order total before payment." },
  { id: "collection", label: "Collection", description: `Free. Collect from our showroom at Bedford Square, Bedfordview. Open ${SHOWROOM.hours.map((row) => `${row.short} ${row.time}`).join(", ")}.` },
] as const;

// 16px text at every width so phones do not zoom into the field.
function Field({ label, id, ...props }: ComponentProps<"input"> & { label: string; id: string }) {
  return <div className="grid gap-2">
    <Label htmlFor={id}>{label}</Label>
    <Input id={id} className="h-11 md:text-base" {...props} />
  </div>;
}

function ShowroomContact() {
  return <address className="grid gap-4 text-sm not-italic sm:grid-cols-2">
    <div className="space-y-1">
      <p className="font-medium">Call us</p>
      {SHOWROOM.phones.map((phone) => <p key={phone.number}>{phone.label}: <a className="underline underline-offset-4" href={`tel:${phone.number.replace(/[^+\d]/g, "")}`}>{phone.number}</a></p>)}
      <p>Email: <a className="break-all underline underline-offset-4" href={`mailto:${SHOWROOM.email}`}>{SHOWROOM.email}</a></p>
    </div>
    <div className="space-y-1">
      <p className="font-medium">Visit the showroom</p>
      <p>{SHOWROOM.address}</p>
      <ul>{SHOWROOM.hours.map((row) => <li key={row.short}>{row.days} {row.time}</li>)}</ul>
    </div>
  </address>;
}

export default function CheckoutPage() {
  const router = useRouter();
  const { capture, attributionHeaders, setSensitiveOverlay } = useStorefrontAnalytics();
  const { bag, error: bagError, busy: bagBusy, update } = useBag();
  const startedCart = useRef("");
  const [fulfillment, setFulfillment] = useState<Fulfillment>("delivery");
  const [checkout, setCheckout] = useState<PreparedCheckout | null>(null);
  const [unavailable, setUnavailable] = useState(false);
  const [paymentStatus, setPaymentStatus] = useState("");
  const [busy, setBusy] = useState(false);
  const [checkoutError, setError] = useState("");
  const error = checkoutError || bagError;
  const errorRef = useRef<HTMLParagraphElement>(null);
  const unavailableRef = useRef<HTMLHeadingElement>(null);
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
      } catch { /* Saved addresses are optional; guest checkout continues. */ }
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
  useEffect(() => { if (unavailable) unavailableRef.current?.focus(); }, [unavailable]);

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
      const payload = await response.json() as { checkout?: PreparedCheckout; message?: string; code?: string };
      if (payload.code === CARD_PAYMENT_UNAVAILABLE) {
        capture({ name: "storefront_friction_noted", properties: { surface: "checkout", kind: "checkout_unavailable" } });
        setUnavailable(true);
        // Release the reservation so the pieces are not held for an order that cannot be paid.
        await update("DELETE", "/api/bag/checkout");
        return;
      }
      if (!response.ok || !payload.checkout) throw new Error(payload.message || "Checkout could not be prepared");
      if (bag?.id) {
        const checkoutType = accountAvailable ? "account" : "guest";
        capture({ name: "storefront_shipping_method_selected", properties: { cart_id: bag.id, method_id: fulfillment } });
        capture({ name: "storefront_checkout_step_completed", properties: { cart_id: bag.id, step: "fulfillment", checkout_type: checkoutType } });
      }
      if (payload.checkout.provider_id === "pp_paystack_checkout" && payload.checkout.redirect_url) {
        const redirect = new URL(payload.checkout.redirect_url);
        if (redirect.origin !== "https://checkout.paystack.com") throw new Error("The hosted payment destination could not be verified");
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
    await update("DELETE", "/api/bag/checkout");
    router.push("/bag");
  }

  const held = isHeld(bag);
  const feedback = error ? purchaseFeedback(error, true) : null;
  const paystack = checkout?.provider_id === "pp_paystack_checkout";
  return <div className="mx-auto w-full max-w-[1400px] px-4 py-10 md:px-6" data-storefront-no-capture="">
    <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_minmax(0,26rem)] lg:items-start">
      <div className="min-w-0 space-y-4">
        {feedback && <p ref={errorRef} id="checkout-error" role={feedback.role} tabIndex={feedback.tabIndex} className="rounded-lg border border-destructive p-4 text-sm text-destructive outline-none">{feedback.message}</p>}
        {unavailable ? <Card data-testid="card-payment-unavailable">
          <CardHeader>
            <CardTitle><h1 ref={unavailableRef} tabIndex={-1} className="text-xl outline-none">Card payment isn’t available yet</h1></CardTitle>
            <CardDescription>No order was placed and nothing was charged. {held ? "" : "Your pieces are no longer reserved. "}To order, call us or visit the showroom and we will help you complete your purchase.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            <ShowroomContact />
            <div className="text-sm font-medium"><Button variant="outline" nativeButton={false} role="link" render={<Link href="/bag" />}>Back to bag</Button></div>
          </CardContent>
        </Card> : checkout ? <Card data-testid={paystack ? "paystack-payment-panel" : "test-payment-panel"}>
          <CardHeader>
            <CardDescription>{paystack ? "Secure hosted payment" : "Test payment only"}</CardDescription>
            <CardTitle><h1 className="text-xl">Payment</h1></CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <p className="text-2xl font-semibold">{money(Number(checkout.amount), checkout.currency_code)}</p>
            <p className="text-muted-foreground">{paystack
              ? "Continue to Paystack to complete your secure payment. Return here to check your order status."
              : "No real payment is taken. Choose an outcome to exercise the local simulator."} You can return to your private order status page to check for updates.</p>
            <p role="status" data-testid="payment-status">Payment status: {paymentStatus || "pending"}</p>
            {paymentStatus === "declined" && <p role="alert">{paystack
              ? "Paystack declined this payment. Do not reuse this checkout session; contact the store before trying another payment."
              : "The test payment was declined. Your bag and reservation remain available until the hold expires."}</p>}
            {paymentStatus === "cancelled" && <p role="status">The test payment was cancelled. You can retry while the reservation is active.</p>}
            {paymentStatus === "pending" && <p role="status">The payment is pending. You can close this page and return to the private order confirmation later.</p>}
            {paymentStatus === "unknown" && <p role="alert">{paystack
              ? "Paystack has not confirmed this payment yet. Do not pay again; wait for the status check or contact the store before retrying."
              : "The payment result is unknown. Your private confirmation page can check again without creating a second order."}</p>}
            {paymentStatus === "paid_exception" && <p role="alert">Payment succeeded, but your order needs attention from the store. Keep your private confirmation page to check for updates.</p>}
            {!paystack && <div className="flex flex-wrap gap-2 font-medium">
              <Button type="button" disabled={busy} onClick={() => void simulate("success")}>Simulate success</Button>
              <Button type="button" variant="outline" disabled={busy} onClick={() => void simulate("pending")}>Simulate pending</Button>
              <Button type="button" variant="outline" disabled={busy} onClick={() => void simulate("declined")}>Simulate decline</Button>
              <Button type="button" variant="outline" disabled={busy} onClick={() => void simulate("cancelled")}>Simulate cancellation</Button>
              <Button type="button" variant="outline" disabled={busy} onClick={() => void simulate("unknown")}>Simulate unknown result</Button>
            </div>}
            <Link className="inline-block font-medium underline underline-offset-4" href="/order/confirmation">Check private order status</Link>
          </CardContent>
        </Card> : <Card>
          <CardHeader>
            <CardTitle><h1 className="text-xl">Checkout</h1></CardTitle>
            <CardDescription>Guest checkout. No account needed.</CardDescription>
          </CardHeader>
          <CardContent>
            {!bag && !error && <p role="status">Loading your bag…</p>}
            {bag && bag.items.length === 0 && <p>Your bag is empty. <Link href="/shop" className="font-medium underline underline-offset-4">Shop all pieces</Link></p>}
            {bag && bag.items.length > 0 && <form ref={formRef} className="grid gap-8" onSubmit={(event) => void prepare(event)}>
              <fieldset className="grid min-w-0 gap-4">
                <legend className="mb-4 font-medium">Contact</legend>
                <Field id="checkout-email" label="Email" name="email" type="email" autoComplete="email" required maxLength={254} />
                <div className="grid gap-4 sm:grid-cols-2">
                  <Field id="checkout-first-name" label="First name" name="first_name" autoComplete="given-name" required maxLength={100} />
                  <Field id="checkout-last-name" label="Last name" name="last_name" autoComplete="family-name" required maxLength={100} />
                </div>
                <Field id="checkout-phone" label="Phone" name="phone" type="tel" autoComplete="tel" required maxLength={40} />
              </fieldset>

              <fieldset className="grid min-w-0 gap-3">
                <legend className="mb-4 font-medium">Delivery or collection</legend>
                {methods.map((method) => <label key={method.id} htmlFor={`fulfillment-${method.id}`} className="flex cursor-pointer items-start gap-3 rounded-md border p-4 has-[:checked]:border-primary">
                  <input id={`fulfillment-${method.id}`} type="radio" name="fulfillment_type" value={method.id} checked={fulfillment === method.id} onChange={() => setFulfillment(method.id)}
                    aria-labelledby={`fulfillment-${method.id}-label`} aria-describedby={`fulfillment-${method.id}-description`} className="mt-0.5 size-4 shrink-0 accent-primary" />
                  <span className="grid gap-1">
                    <span id={`fulfillment-${method.id}-label`} className="text-sm leading-none font-medium">{method.label}</span>
                    <span id={`fulfillment-${method.id}-description`} className="text-sm text-muted-foreground">{method.description}</span>
                  </span>
                </label>)}
              </fieldset>

              {fulfillment === "delivery" ? <fieldset className="grid min-w-0 gap-4">
                <legend className="mb-4 font-medium">Delivery address</legend>
                {savedAddresses.length > 0 && <Select label="Use a saved address" defaultValue="" onChange={(value) => fillSavedAddress(value || "")} data={[{ value: "", label: "Enter a new address" }, ...savedAddresses.map((address) => ({ value: address.id, label: `${address.address_1}${address.address_2 ? `, ${address.address_2}` : ""} — ${address.city}` }))]} />}
                <Field id="checkout-address-1" label="Street address" name="address_1" autoComplete="address-line1" required maxLength={250} />
                <Field id="checkout-address-2" label="Suburb or area" name="address_2" autoComplete="address-line2" required maxLength={150} aria-describedby="checkout-suburb-note" />
                <p id="checkout-suburb-note" className="-mt-2 text-sm text-muted-foreground">We deliver in selected Gauteng areas.</p>
                <div className="grid gap-4 sm:grid-cols-2">
                  <Field id="checkout-city" label="City" name="city" autoComplete="address-level2" required maxLength={100} />
                  <Field id="checkout-province" label="Province" name="province" autoComplete="address-level1" required maxLength={100} defaultValue="Gauteng" />
                </div>
                <Field id="checkout-postal-code" label="Postal code" name="postal_code" inputMode="numeric" autoComplete="postal-code" pattern="[0-9]{4}" required />
                {accountAvailable && <Checkbox checked={saveAddress} onChange={(event) => setSaveAddress(event.target.checked)} label="Save this address to your account for next time" />}
              </fieldset> : <section aria-labelledby="collection-heading" className="space-y-2 rounded-md bg-muted/50 p-4 text-sm">
                <h2 id="collection-heading" className="font-medium">Collect from {SHOWROOM.name}</h2>
                <address className="not-italic">{SHOWROOM.address}</address>
                <p className="text-muted-foreground">{SHOWROOM.note}</p>
                <ul>{SHOWROOM.hours.map((row) => <li key={row.short}>{row.days} {row.time}</li>)}</ul>
                <p className="text-muted-foreground">We will contact you when your order is ready to collect.</p>
              </section>}

              {/* Mantine's unlayered button reset makes buttons inherit their font, so the wrapper carries it. */}
              <div className="grid gap-3 text-sm font-medium">
                <Button type="submit" size="lg" className="h-12 w-full" disabled={busy || bagBusy || !held}>{busy ? "Checking order…" : "Continue to payment"}</Button>
                {!held && <p role="alert" className="font-normal">Your reservation expired. Return to your bag to review and reserve the pieces again.</p>}
              </div>
            </form>}
          </CardContent>
        </Card>}
      </div>

      {bag && bag.items.length > 0 && <Card className="min-w-0">
        <CardHeader>
          <CardTitle><h2>Your order</h2></CardTitle>
          <CardDescription>Prices in rand, VAT included.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <ul className="space-y-3">{bag.items.map((item) => <li key={item.id} className="flex gap-3 text-sm">
            <div className="size-16 shrink-0 overflow-hidden rounded-md bg-muted"><PieceImage product={{ title: item.title, thumbnail: item.thumbnail }} className="min-h-0" /></div>
            <div className="min-w-0 flex-1">
              <p className="font-medium">{item.title}</p>
              <p className="text-muted-foreground">Qty {item.quantity}</p>
              {item.fulfillment_promise?.kind === "made_to_order" && <p className="text-xs text-muted-foreground">Made to order · {promiseDates(item.fulfillment_promise.estimated_from, item.fulfillment_promise.estimated_by)}</p>}
            </div>
            <p className="font-medium whitespace-nowrap">{money(item.total, bag.currency_code)}</p>
          </li>)}</ul>
          {bag.hold?.fulfillment_promise && <div className="space-y-1 text-sm" role="status" data-testid="checkout-fulfillment-promise">
            <p className="font-medium">One fulfillment promise for your full order</p>
            <p className="text-muted-foreground">{bag.hold.fulfillment_promise.kind === "mixed" ? "All pieces will be fulfilled together when the made-to-order pieces are ready." : bag.hold.fulfillment_promise.kind === "made_to_order" ? "This order is made to order." : "All pieces are in stock."}</p>
            <p className="text-muted-foreground">Estimated ready {promiseDates(bag.hold.fulfillment_promise.estimated_from, bag.hold.fulfillment_promise.estimated_by)}.</p>
          </div>}
          <BagTotals bag={bag} delivery={fulfillment === "collection" ? "Free" : DELIVERY_COST} />
          {checkout && <div className="flex justify-between gap-4 border-t pt-2 font-medium"><span>Total to pay</span><span data-testid="checkout-total">{money(Number(checkout.amount), checkout.currency_code)}</span></div>}
          <p className="text-xs text-muted-foreground">{fulfillment === "delivery" ? "Plus delivery, confirmed before payment. " : ""}Prices and availability are confirmed before payment.</p>
          {held && <p className="text-xs text-muted-foreground">Your pieces are reserved until {new Date(bag.hold!.expires_at).toLocaleTimeString("en-ZA")}.</p>}
          {!checkout && !unavailable && <div className="text-sm font-medium"><Button type="button" variant="outline" className="w-full" disabled={busy || bagBusy} onClick={() => void releaseHold()}>Edit bag</Button></div>}
        </CardContent>
      </Card>}
    </div>
  </div>;
}
