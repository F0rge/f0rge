"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useStorefrontAnalytics } from "@/components/analytics/analytics-provider";
import { ANALYTICS_CUSTOMER_TYPE_HEADER } from "@/lib/analytics/attribution";
import { confirmedPaymentStep } from "@/lib/analytics/commerce-events";
import { fulfillmentStatusLabel } from "@/lib/order-fulfillment";

type Confirmation = {
  status: "captured" | "pending" | "processing" | "declined" | "cancelled" | "paid_exception" | "unknown";
  order?: {
    reference: number;
    analytics_order_id?: string;
    email: string;
    currency_code: string;
    subtotal: number;
    shipping_total: number;
    tax_total: number;
    total: number;
    fulfillment_type?: string;
    fulfillment_status?: string;
    fulfillment_revision?: number;
    refund_status?: {
      refunded_amount_minor: number;
      items: { amount_minor: number; currency_code: string; status: "pending" | "succeeded" | "failed" }[];
    } | null;
    fulfillment_promise?: {
      kind?: string;
      accepted_at?: string;
      estimated_from?: string;
      estimated_by?: string;
    } | null;
    items: {
      title: string;
      quantity: number;
      unit_price: number;
      total: number;
      fulfillment_promise?: { estimated_from?: string; estimated_by?: string } | null;
    }[];
    shipping: { name: string; total: number }[];
    address: { first_name: string; last_name: string; address_1: string; address_2?: string; city: string; province: string; postal_code: string } | null;
  };
};
const money = (value: number, currency = "ZAR") => new Intl.NumberFormat("en-ZA", { style: "currency", currency }).format(value);
const refundLabels: Record<string, string> = {
  pending: "Refund is processing",
  succeeded: "Refund sent",
  failed: "Refund could not be completed",
};

export default function OrderConfirmationPage() {
  const { attributionHeaders, capture, setSensitiveOverlay } = useStorefrontAnalytics();
  const [result, setResult] = useState<Confirmation | null>(null);
  const notedPayment = useRef<string | null>(null);
  const [unavailable, setUnavailable] = useState(false);
  const emailAccess = useRef<{ order_id: string; access_token: string } | null>(null);
  const load = useCallback(async () => {
    try {
      const capability = emailAccess.current;
      const analyticsHeaders = attributionHeaders();
      const response = await fetch("/api/order/confirmation", {
        method: capability ? "POST" : "GET",
        headers: capability ? { "content-type": "application/json", ...analyticsHeaders } : analyticsHeaders,
        body: capability ? JSON.stringify(capability) : undefined,
        cache: "no-store",
      });
      if (!response.ok) throw new Error("not available");
      const payload = await response.json() as Confirmation;
      setResult(payload);
      setUnavailable(false);
      if (capability) emailAccess.current = null;
    } catch {
      setUnavailable(true);
    }
  }, [attributionHeaders]);
  useEffect(() => {
    setSensitiveOverlay(true);
    return () => setSensitiveOverlay(false);
  }, [setSensitiveOverlay]);
  useEffect(() => {
    const step = confirmedPaymentStep({
      status: result?.status,
      analyticsOrderId: result?.order?.analytics_order_id,
      customerType: attributionHeaders()[ANALYTICS_CUSTOMER_TYPE_HEADER] ?? null,
    });
    if (!step) return;
    const orderId = step.properties.cart_id;
    if (notedPayment.current === orderId) return;
    const storageKey = `storefront-payment-step:${orderId}`;
    try {
      if (window.sessionStorage.getItem(storageKey) === "1") {
        notedPayment.current = orderId;
        return;
      }
      window.sessionStorage.setItem(storageKey, "1");
    } catch { /* A private session still emits once for this page load. */ }
    notedPayment.current = orderId;
    capture(step);
  }, [attributionHeaders, capture, result]);
  useEffect(() => {
    const fragment = new URLSearchParams(window.location.hash.replace(/^#/, ""));
    const orderId = fragment.get("order_id");
    const accessToken = fragment.get("access");
    if (orderId && accessToken && /^order_[A-Za-z0-9_-]+$/.test(orderId) && /^[A-Za-z0-9_-]{43}$/.test(accessToken)) {
      emailAccess.current = { order_id: orderId, access_token: accessToken };
      window.history.replaceState(null, "", `${window.location.pathname}${window.location.search}`);
    }
    void load();
    const timer = window.setInterval(() => void load(), 2500);
    return () => window.clearInterval(timer);
  }, [load]);

  return <div className="content confirmation-page" data-storefront-no-capture="">
    <p className="eyebrow">The Collector / private order confirmation</p>
    {!result && !unavailable && <p role="status">Checking your order…</p>}
    {unavailable && <div role="alert"><h1>Confirmation temporarily unavailable</h1><p>Refresh this page to check again. Order details are available only through the private checkout capability saved in this browser.</p><button type="button" onClick={() => void load()}>Check again</button></div>}
    {result?.status === "captured" && result.order && <>
      <h1>Thank you. Your order is confirmed.</h1>
      <p role="status">Private order reference {result.order.reference} · contact email {result.order.email}</p>
      <div className="confirmation-card">
        <section aria-live="polite">
          <h2>Fulfilment status</h2>
          <p role="status">{fulfillmentStatusLabel(result.order.fulfillment_status || "confirmed")}</p>
          {result.order.fulfillment_promise?.estimated_from && result.order.fulfillment_promise.estimated_by && <p>
            {result.order.fulfillment_promise.estimated_from === result.order.fulfillment_promise.estimated_by
              ? `Estimated ready ${result.order.fulfillment_promise.estimated_by}`
              : `Estimated ready ${result.order.fulfillment_promise.estimated_from} – ${result.order.fulfillment_promise.estimated_by}`}
          </p>}
        </section>
        <h2>Order summary</h2>
        {result.order.items.map((item, index) => <div className="checkout-summary-line" key={item.title + "-" + index}>
          <span>{item.title} × {item.quantity}{item.fulfillment_promise?.estimated_from && item.fulfillment_promise.estimated_by && <small className="block">
            {item.fulfillment_promise.estimated_from === item.fulfillment_promise.estimated_by
              ? `Ready ${item.fulfillment_promise.estimated_by}`
              : `Ready ${item.fulfillment_promise.estimated_from} – ${item.fulfillment_promise.estimated_by}`}
          </small>}</span>
          <strong>{money(item.total, result.order!.currency_code.toUpperCase())}</strong>
        </div>)}
        {result.order.shipping.map((method, index) => <div className="checkout-summary-line" key={method.name + "-" + index}><span>{method.name}</span><strong>{money(method.total, result.order!.currency_code.toUpperCase())}</strong></div>)}
        <dl><dt>Subtotal</dt><dd>{money(result.order.subtotal, result.order.currency_code.toUpperCase())}</dd><dt>VAT included</dt><dd>{money(result.order.tax_total, result.order.currency_code.toUpperCase())}</dd><dt>Total paid</dt><dd>{money(result.order.total, result.order.currency_code.toUpperCase())}</dd></dl>
        {result.order.refund_status?.items.length ? <section aria-live="polite">
          <h2>Refund status</h2>
          {result.order.refund_status.items.map((refund, index) => <p key={`${refund.status}-${refund.amount_minor}-${index}`} role="status">
            {refundLabels[refund.status] || "Refund status updated"} · {money(refund.amount_minor / 100, refund.currency_code)}
          </p>)}
        </section> : null}
        {result.order.address && <section><h3>{result.order.fulfillment_type === "collection" ? "Collection" : "Delivery"}</h3><p>{result.order.address.first_name} {result.order.address.last_name}<br />{result.order.address.address_1}{result.order.address.address_2 ? ", " + result.order.address.address_2 : ""}<br />{result.order.address.city}, {result.order.address.province} {result.order.address.postal_code}</p></section>}
      </div>
    </>}
    {result?.status === "pending" && <div role="status"><h1>Payment is pending</h1><p>This private page will update when the payment result arrives. You can close the browser and return to this page later.</p></div>}
    {result?.status === "unknown" && <div role="alert"><h1>Payment result is unknown</h1><p>We could not confirm the result yet. Keep this private page open or return later to check again; another order will not be created by checking.</p><button type="button" onClick={() => void load()}>Check again</button></div>}
    {result?.status === "processing" && <div role="status"><h1>Payment received</h1><p>Your order is being committed. This page will update automatically.</p></div>}
    {result?.status === "declined" && <div role="alert"><h1>Payment was declined</h1><p>No paid order was created. Return to your bag and try again while your reservation is active.</p><Link href="/bag" className="text-link">Return to your bag ↗</Link></div>}
    {result?.status === "cancelled" && <div role="status"><h1>Payment was cancelled</h1><p>No paid order was created. You can return to your bag to retry before the reservation expires.</p><Link href="/bag" className="text-link">Return to your bag ↗</Link></div>}
    {result?.status === "paid_exception" && <div role="alert"><h1>Payment succeeded; inventory review is underway</h1><p>Your payment is recorded, but the order reservation needs recovery. This status is retained for follow-up.</p></div>}
    <Link href="/shop" className="text-link">Continue browsing ↗</Link>
  </div>;
}
