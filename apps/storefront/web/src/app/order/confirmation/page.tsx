"use client";

import { Button, Card, CardContent } from "@f0rge/ui";
import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useStorefrontAnalytics } from "@/components/analytics/analytics-provider";
import { ANALYTICS_CUSTOMER_TYPE_HEADER } from "@/lib/analytics/attribution";
import { confirmedPaymentStep } from "@/lib/analytics/commerce-events";
import { fulfillmentStatusLabel } from "@/lib/order-fulfillment";
import { formatCustomerPrice } from "@/lib/order-money";

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
const money = (value: number, currency?: string) => formatCustomerPrice(value, currency);
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

  const line = "flex justify-between gap-4 border-t py-3";
  const link = "inline-flex min-h-11 items-center text-sm font-medium underline underline-offset-4";
  // Mantine's unlayered button reset makes buttons inherit their font, so the wrappers carry it.
  return <div className="mx-auto w-full max-w-3xl space-y-6 px-4 py-10 md:px-6" data-storefront-no-capture="">
    {!result && !unavailable && <p role="status">Checking your order…</p>}
    {unavailable && <div role="alert" className="space-y-3"><h1 className="text-2xl font-semibold">Confirmation temporarily unavailable</h1><p className="text-muted-foreground">Refresh this page to check again. Open your private confirmation link or return in the browser you used at checkout.</p><div className="text-sm font-medium"><Button type="button" className="h-11 px-4" onClick={() => void load()}>Check again</Button></div></div>}
    {result?.status === "captured" && result.order && <>
      <div className="space-y-2">
        <h1 className="text-2xl font-semibold">Thank you. Your order is confirmed.</h1>
        <p role="status" className="text-muted-foreground">Private order reference {result.order.reference} · contact email {result.order.email}</p>
      </div>
      <Card>
        <CardContent className="space-y-6">
          <section aria-live="polite" className="space-y-1">
            <h2 className="text-lg font-medium">Fulfilment status</h2>
            <p role="status">{fulfillmentStatusLabel(result.order.fulfillment_status || "confirmed")}</p>
            {result.order.fulfillment_promise?.estimated_from && result.order.fulfillment_promise.estimated_by && <p className="text-muted-foreground">
              {result.order.fulfillment_promise.estimated_from === result.order.fulfillment_promise.estimated_by
                ? `Estimated ready ${result.order.fulfillment_promise.estimated_by}`
                : `Estimated ready ${result.order.fulfillment_promise.estimated_from} – ${result.order.fulfillment_promise.estimated_by}`}
            </p>}
          </section>
          <section>
            <h2 className="mb-2 text-lg font-medium">Order summary</h2>
            {result.order.items.map((item, index) => <div className={line} key={item.title + "-" + index}>
              <span>{item.title} × {item.quantity}{item.fulfillment_promise?.estimated_from && item.fulfillment_promise.estimated_by && <small className="block text-muted-foreground">
                {item.fulfillment_promise.estimated_from === item.fulfillment_promise.estimated_by
                  ? `Ready ${item.fulfillment_promise.estimated_by}`
                  : `Ready ${item.fulfillment_promise.estimated_from} – ${item.fulfillment_promise.estimated_by}`}
              </small>}</span>
              <strong className="font-medium whitespace-nowrap">{money(item.total, result.order!.currency_code)}</strong>
            </div>)}
            {result.order.shipping.map((method, index) => <div className={line} key={method.name + "-" + index}><span>{method.name}</span><strong className="font-medium whitespace-nowrap">{money(method.total, result.order!.currency_code)}</strong></div>)}
            <dl className="grid grid-cols-[minmax(0,1fr)_auto] gap-2 border-t pt-3"><dt className="text-muted-foreground">Subtotal</dt><dd className="text-right">{money(result.order.subtotal, result.order.currency_code)}</dd><dt className="text-muted-foreground">VAT included</dt><dd className="text-right">{money(result.order.tax_total, result.order.currency_code)}</dd><dt className="font-medium">Total paid</dt><dd className="text-right font-medium">{money(result.order.total, result.order.currency_code)}</dd></dl>
          </section>
          {result.order.refund_status?.items.length ? <section aria-live="polite" className="space-y-1">
            <h2 className="text-lg font-medium">Refund status</h2>
            {result.order.refund_status.items.map((refund, index) => <p key={`${refund.status}-${refund.amount_minor}-${index}`} role="status">
              {refundLabels[refund.status] || "Refund status updated"} · {money(refund.amount_minor / 100, refund.currency_code)}
            </p>)}
          </section> : null}
          {result.order.address && <section className="space-y-1"><h3 className="font-medium">{result.order.fulfillment_type === "collection" ? "Collection" : "Delivery"}</h3><p className="text-muted-foreground">{result.order.address.first_name} {result.order.address.last_name}<br />{result.order.address.address_1}{result.order.address.address_2 ? ", " + result.order.address.address_2 : ""}<br />{result.order.address.city}, {result.order.address.province} {result.order.address.postal_code}</p></section>}
        </CardContent>
      </Card>
    </>}
    {result?.status === "pending" && <div role="status" className="space-y-2"><h1 className="text-2xl font-semibold">Payment is pending</h1><p className="text-muted-foreground">This private page will update when the payment result arrives. You can close the browser and return to this page later.</p></div>}
    {result?.status === "unknown" && <div role="alert" className="space-y-3"><h1 className="text-2xl font-semibold">Payment result is unknown</h1><p className="text-muted-foreground">We could not confirm the result yet. Keep this private page open or return later to check again; another order will not be created by checking.</p><div className="text-sm font-medium"><Button type="button" className="h-11 px-4" onClick={() => void load()}>Check again</Button></div></div>}
    {result?.status === "processing" && <div role="status" className="space-y-2"><h1 className="text-2xl font-semibold">Payment received</h1><p className="text-muted-foreground">Your order is being committed. This page will update automatically.</p></div>}
    {result?.status === "declined" && <div role="alert" className="space-y-2"><h1 className="text-2xl font-semibold">Payment was declined</h1><p className="text-muted-foreground">No paid order was created. Return to your bag and try again while your reservation is active.</p><Link href="/bag" className={link}>Return to your bag</Link></div>}
    {result?.status === "cancelled" && <div role="status" className="space-y-2"><h1 className="text-2xl font-semibold">Payment was cancelled</h1><p className="text-muted-foreground">No paid order was created. You can return to your bag to retry before the reservation expires.</p><Link href="/bag" className={link}>Return to your bag</Link></div>}
    {result?.status === "paid_exception" && <div role="alert" className="space-y-2"><h1 className="text-2xl font-semibold">Payment succeeded; inventory review is underway</h1><p className="text-muted-foreground">Your payment is recorded, but the order reservation needs recovery. This status is retained for follow-up.</p></div>}
    <Link href="/shop" className={link}>Continue browsing</Link>
  </div>;
}
