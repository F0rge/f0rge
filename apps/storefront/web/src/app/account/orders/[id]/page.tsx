import type { Metadata } from "next";
import Link from "next/link";
import { customerMedusaFetch, getCustomerContext } from "@/lib/customer-auth";
import { fulfillmentStatusLabel, storefrontOrderFulfillment } from "@/lib/order-fulfillment";
import { orderMoney as money } from "@/lib/order-money";
import { orderRefundStatus, paidOrderHistory } from "@/lib/order-history";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Order details", robots: { index: false, follow: false, noarchive: true }, referrer: "no-referrer" };

type OrderView = {
  id: string;
  display_id?: number;
  status?: string;
  fulfillment_type?: string;
  fulfillment_status?: string;
  currency_code?: string;
  total?: number | string;
  subtotal?: number | string;
  shipping_total?: number | string;
  tax_total?: number | string;
  items?: { id?: string; title?: string; quantity?: number; total?: number | string }[];
  shipping_methods?: { name?: string; total?: number | string }[];
  refund_status?: ReturnType<typeof orderRefundStatus>;
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
        "id", "display_id", "status", "currency_code", "total", "subtotal", "shipping_total", "tax_total", "metadata",
        "items.id", "items.title", "items.quantity", "items.total", "shipping_methods.name", "shipping_methods.total",
      ].join(",");
      const result = await customerMedusaFetch(customer, `/store/orders/${encodeURIComponent(id)}?fields=${fields}`);
      if (result.status >= 200 && result.status < 300 && result.payload.order && typeof result.payload.order === "object") {
        const raw = result.payload.order as OrderView & Record<string, unknown>;
        const history = paidOrderHistory(raw);
        const fulfillment = storefrontOrderFulfillment(raw);
        order = { ...raw, ...fulfillment, total: history?.total ?? raw.total, refund_status: orderRefundStatus(raw),
          items: raw.items?.map((item) => ({ ...item,
            total: (typeof item.id === "string" ? history?.items.get(item.id) : undefined) ?? item.total,
          })),
        };
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
    <section className="account-panel" aria-label="Fulfilment status">
      <h2>Fulfilment</h2>
      <p role="status">{fulfillmentStatusLabel(order.fulfillment_status)}</p>
      <p>{order.fulfillment_type === "collection" ? "Showroom collection" : "Delivery"}</p>
    </section>
    {order.refund_status && <section className="account-panel" aria-label="Refund status">
      <h2>Refunds</h2>
      <p>Returned to your payment method: {money(order.refund_status.refunded_amount_minor / 100, currency)}</p>
      {order.refund_status.items.map((refund, index) => <p key={index}>
        {money(refund.amount_minor / 100, refund.currency_code)} — {refund.status === "succeeded" ? "Refunded" : refund.status === "pending" ? "Pending confirmation" : "Refund failed"}
      </p>)}
    </section>}
    <section className="account-panel" aria-label="Order details">
      <h2>Items</h2>
      {(order.items || []).map((item, index) => <div className="checkout-summary-line" key={`${item.title || "item"}-${index}`}>
        <span>{item.title || "Item"} × {item.quantity || 0}</span><strong>{money(item.total, currency)}</strong>
      </div>)}
      {(order.shipping_methods || []).map((method, index) => <div className="checkout-summary-line" key={`${method.name || "shipping"}-${index}`}>
        <span>{method.name || "Shipping"}</span><strong>{money(method.total, currency)}</strong>
      </div>)}
      <dl><dt>Subtotal</dt><dd>{money(order.subtotal, currency)}</dd><dt>Shipping</dt><dd>{money(order.shipping_total, currency)}</dd>
        <dt>VAT included</dt><dd>{money(order.tax_total, currency)}</dd><dt>Total paid</dt><dd>{money(order.total, currency)}</dd></dl>
    </section>
    <Link href="/account" className="text-link">Back to your orders ↗</Link>
  </div>;
}

function OrderUnavailable() {
  return <div className="content account-page account-order-detail"><h1>Order not found</h1><p>This order is unavailable in your account.</p><Link href="/account" className="text-link">Back to your account ↗</Link></div>;
}
