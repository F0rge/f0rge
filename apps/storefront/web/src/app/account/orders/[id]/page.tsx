import type { Metadata } from "next";
import Link from "next/link";
import { customerMedusaFetch, getCustomerContext } from "@/lib/customer-auth";
import { orderMoney as money } from "@/lib/order-money";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Order details", robots: { index: false, follow: false, noarchive: true }, referrer: "no-referrer" };

type OrderView = {
  id: string;
  display_id?: number;
  status?: string;
  currency_code?: string;
  total?: number | string;
  subtotal?: number | string;
  shipping_total?: number | string;
  tax_total?: number | string;
  items?: { title?: string; quantity?: number; total?: number | string }[];
  shipping_methods?: { name?: string; total?: number | string }[];
};

export default async function AccountOrderPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  if (!/^order_[A-Za-z0-9_-]+$/.test(id)) return <OrderUnavailable />;
  let order: OrderView | null = null;
  let signedIn = false;
  try {
    const customer = await getCustomerContext();
    signedIn = Boolean(customer);
    if (customer) {
      const fields = [
        "id", "display_id", "status", "currency_code", "total", "subtotal", "shipping_total", "tax_total",
        "items.title", "items.quantity", "items.total", "shipping_methods.name", "shipping_methods.total",
      ].join(",");
      const result = await customerMedusaFetch(customer, `/store/orders/${encodeURIComponent(id)}?fields=${fields}`);
      if (result.status >= 200 && result.status < 300 && result.payload.order && typeof result.payload.order === "object") {
        order = result.payload.order as OrderView;
      }
    }
  } catch { /* Keep account order errors private and generic. */ }

  if (!order) return <div className="content account-page account-order-detail">
    <p className="eyebrow">The Collector / customer account</p>
    <h1>{signedIn ? "Order not found" : "Sign in to view this order"}</h1>
    <p className="account-error">{signedIn ? "This order is unavailable in your account." : "Order details are shown only to the signed-in customer."}</p>
    <Link href={signedIn ? "/account" : "/account/sign-in"} className="text-link">{signedIn ? "Back to your account ↗" : "Continue with email ↗"}</Link>
  </div>;

  const currency = order.currency_code || "ZAR";
  return <div className="content account-page account-order-detail">
    <p className="eyebrow">The Collector / customer account</p>
    <h1>Order {order.display_id ?? order.id}</h1>
    <p>Order status: {order.status || "pending"}</p>
    <section className="account-panel" aria-label="Order details">
      <h2>Items</h2>
      {(order.items || []).map((item, index) => <div className="checkout-summary-line" key={`${item.title || "item"}-${index}`}>
        <span>{item.title || "Item"} × {item.quantity || 0}</span><strong>{money(item.total, currency)}</strong>
      </div>)}
      {(order.shipping_methods || []).map((method, index) => <div className="checkout-summary-line" key={`${method.name || "shipping"}-${index}`}>
        <span>{method.name || "Shipping"}</span><strong>{money(method.total, currency)}</strong>
      </div>)}
      <dl><dt>Subtotal</dt><dd>{money(order.subtotal, currency)}</dd><dt>Shipping</dt><dd>{money(order.shipping_total, currency)}</dd>
        <dt>VAT included</dt><dd>{money(order.tax_total, currency)}</dd><dt>Total</dt><dd>{money(order.total, currency)}</dd></dl>
    </section>
    <Link href="/account" className="text-link">Back to your orders ↗</Link>
  </div>;
}

function OrderUnavailable() {
  return <div className="content account-page account-order-detail"><h1>Order not found</h1><p>This order is unavailable in your account.</p><Link href="/account" className="text-link">Back to your account ↗</Link></div>;
}
