"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";

type Confirmation = {
  status: "captured" | "pending" | "processing" | "declined" | "cancelled" | "paid_exception" | "unknown";
  order?: {
    reference: number;
    email: string;
    currency_code: string;
    subtotal: number;
    shipping_total: number;
    tax_total: number;
    total: number;
    fulfillment_type?: string;
    items: { title: string; quantity: number; unit_price: number; total: number }[];
    shipping: { name: string; total: number }[];
    address: { first_name: string; last_name: string; address_1: string; address_2?: string; city: string; province: string; postal_code: string } | null;
  };
};
const money = (value: number, currency = "ZAR") => new Intl.NumberFormat("en-ZA", { style: "currency", currency }).format(value);

export default function OrderConfirmationPage() {
  const [result, setResult] = useState<Confirmation | null>(null);
  const [unavailable, setUnavailable] = useState(false);
  const load = useCallback(async () => {
    try {
      const response = await fetch("/api/order/confirmation", { cache: "no-store" });
      if (!response.ok) throw new Error("not available");
      const payload = await response.json() as Confirmation;
      setResult(payload);
      setUnavailable(false);
    } catch {
      setUnavailable(true);
    }
  }, []);
  useEffect(() => {
    void load();
    const timer = window.setInterval(() => void load(), 2500);
    return () => window.clearInterval(timer);
  }, [load]);

  return <div className="content confirmation-page">
    <p className="eyebrow">The Collector / private order confirmation</p>
    {!result && !unavailable && <p role="status">Checking your order…</p>}
    {unavailable && <div role="alert"><h1>Confirmation temporarily unavailable</h1><p>Refresh this page to check again. Order details are available only through the private checkout capability saved in this browser.</p><button type="button" onClick={() => void load()}>Check again</button></div>}
    {result?.status === "captured" && result.order && <>
      <h1>Thank you. Your order is confirmed.</h1>
      <p role="status">Private order reference {result.order.reference} · confirmation sent to {result.order.email}</p>
      <div className="confirmation-card">
        <h2>Order summary</h2>
        {result.order.items.map((item, index) => <div className="checkout-summary-line" key={item.title + "-" + index}><span>{item.title} × {item.quantity}</span><strong>{money(item.total, result.order!.currency_code.toUpperCase())}</strong></div>)}
        {result.order.shipping.map((method, index) => <div className="checkout-summary-line" key={method.name + "-" + index}><span>{method.name}</span><strong>{money(method.total, result.order!.currency_code.toUpperCase())}</strong></div>)}
        <dl><dt>Subtotal</dt><dd>{money(result.order.subtotal, result.order.currency_code.toUpperCase())}</dd><dt>VAT included</dt><dd>{money(result.order.tax_total, result.order.currency_code.toUpperCase())}</dd><dt>Total paid</dt><dd>{money(result.order.total, result.order.currency_code.toUpperCase())}</dd></dl>
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
