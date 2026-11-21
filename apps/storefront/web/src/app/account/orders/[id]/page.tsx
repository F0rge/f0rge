import type { Metadata } from "next";
import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@f0rge/ui";
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
  fulfillment_type?: string | null;
  fulfillment_status?: string | null;
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

  if (!order) return <OrderUnavailable heading={signedIn ? "Order not found" : "Sign in to view this order"}
    message={signedIn ? "This order is unavailable in your account." : "Order details are shown only to the signed-in customer."}
    href={signedIn ? "/account" : "/account/sign-in"} label={signedIn ? "Back to your account" : "Continue with email"} />;

  const currency = order.currency_code || "ZAR";
  const line = "flex justify-between gap-4 border-t py-3";
  return <div className="mx-auto w-full max-w-3xl space-y-6 px-4 py-10 md:px-6">
    <h1 className="text-2xl font-semibold">Order {order.display_id ?? order.id}</h1>
    {order.fulfillment_status || order.fulfillment_type ? <Card role="region" aria-label="Fulfilment status">
      <CardHeader><CardTitle><h2 className="text-xl">Fulfilment</h2></CardTitle></CardHeader>
      <CardContent className="space-y-1">
        {order.fulfillment_status ? <p role="status">{fulfillmentStatusLabel(order.fulfillment_status)}</p> : null}
        {order.fulfillment_type === "collection" ? <p className="text-muted-foreground">Showroom collection</p> : null}
        {order.fulfillment_type === "delivery" ? <p className="text-muted-foreground">Delivery</p> : null}
      </CardContent>
    </Card> : null}
    {order.refund_status && <Card role="region" aria-label="Refund status">
      <CardHeader><CardTitle><h2 className="text-xl">Refunds</h2></CardTitle></CardHeader>
      <CardContent className="space-y-1">
        <p>Returned to your payment method: {money(order.refund_status.refunded_amount_minor / 100, currency)}</p>
        {order.refund_status.items.map((refund, index) => <p key={index} className="text-muted-foreground">
          {money(refund.amount_minor / 100, refund.currency_code)} — {refund.status === "succeeded" ? "Refunded" : refund.status === "pending" ? "Pending confirmation" : "Refund failed"}
        </p>)}
      </CardContent>
    </Card>}
    <Card role="region" aria-label="Order details">
      <CardHeader><CardTitle><h2 className="text-xl">Items</h2></CardTitle></CardHeader>
      <CardContent>
        {(order.items || []).map((item, index) => <div className={line} key={`${item.title || "item"}-${index}`}>
          <span>{item.title || "Item"} × {item.quantity || 0}</span><strong className="font-medium whitespace-nowrap">{money(item.total, currency)}</strong>
        </div>)}
        {(order.shipping_methods || []).map((method, index) => <div className={line} key={`${method.name || "shipping"}-${index}`}>
          <span>{method.name || "Shipping"}</span><strong className="font-medium whitespace-nowrap">{money(method.total, currency)}</strong>
        </div>)}
        <dl className="grid grid-cols-[minmax(0,1fr)_auto] gap-2 border-t pt-3"><dt className="text-muted-foreground">Subtotal</dt><dd className="text-right">{money(order.subtotal, currency)}</dd><dt className="text-muted-foreground">Shipping</dt><dd className="text-right">{money(order.shipping_total, currency)}</dd>
          <dt className="text-muted-foreground">VAT included</dt><dd className="text-right">{money(order.tax_total, currency)}</dd><dt className="font-medium">Total paid</dt><dd className="text-right font-medium">{money(order.total, currency)}</dd></dl>
      </CardContent>
    </Card>
    <Link href="/account" className="inline-flex min-h-11 items-center text-sm font-medium underline underline-offset-4">Back to your orders</Link>
  </div>;
}

function OrderUnavailable({ heading = "Order not found", message = "This order is unavailable in your account.", href = "/account", label = "Back to your account" }) {
  return <div className="mx-auto w-full max-w-3xl space-y-4 px-4 py-10 md:px-6">
    <h1 className="text-2xl font-semibold">{heading}</h1>
    <p className="text-muted-foreground">{message}</p>
    <Link href={href} className="inline-flex min-h-11 items-center text-sm font-medium underline underline-offset-4">{label}</Link>
  </div>;
}
