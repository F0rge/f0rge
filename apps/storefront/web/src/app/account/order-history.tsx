"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { Button } from "@f0rge/ui";
import { orderMoney as money } from "@/lib/order-money";

type OrderSummary = {
  id: string;
  reference: number | null;
  created_at: string | null;
  currency_code: string;
  status: string;
  total: string | number | null;
};

function orderLabel(order: OrderSummary): string {
  return `Order ${order.reference ?? order.id}`;
}

export function OrderHistory() {
  const [orders, setOrders] = useState<OrderSummary[]>([]);
  const [claimable, setClaimable] = useState<OrderSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [hasMore, setHasMore] = useState(false);
  const [busyId, setBusyId] = useState("");
  const [error, setError] = useState("");

  const load = useCallback(async (offset = 0, append = false) => {
    const response = await fetch(`/api/account/orders?offset=${offset}`, { cache: "no-store" });
    const payload = await response.json() as { orders?: OrderSummary[]; claimable?: OrderSummary[]; hasMore?: boolean; message?: string };
    if (!response.ok) throw new Error(payload.message || "Your orders are unavailable");
    setOrders((current) => append ? [...current, ...(payload.orders || [])] : payload.orders || []);
    if (!append) setClaimable(payload.claimable || []);
    setHasMore(payload.hasMore === true);
  }, []);

  useEffect(() => {
    void load().catch((reason) => setError(reason instanceof Error ? reason.message : "Your orders are unavailable"))
      .finally(() => setLoading(false));
  }, [load]);

  async function claim(orderId: string) {
    setBusyId(orderId); setError("");
    try {
      const response = await fetch(`/api/account/orders/${encodeURIComponent(orderId)}/claim`, { method: "POST", cache: "no-store" });
      const payload = await response.json() as { message?: string };
      if (!response.ok) throw new Error(payload.message || "This order could not be linked");
      await load(0);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "This order could not be linked");
    } finally {
      setBusyId("");
    }
  }

  async function loadMore() {
    setError("");
    try { await load(orders.length, true); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Your orders are unavailable"); }
  }

  return <section className="account-panel account-orders" aria-labelledby="order-history-heading">
    <h2 id="order-history-heading">Your orders</h2>
    {loading ? <p role="status">Loading your orders…</p> : error && !orders.length && !claimable.length
      ? <p role="alert" className="account-error">{error}</p>
      : orders.length ? <ul className="account-order-list">{orders.map((order) => <li key={order.id}>
        <div><strong>{orderLabel(order)}</strong><p>{order.created_at ? new Date(order.created_at).toLocaleDateString("en-ZA") : "Date unavailable"} · {order.status}</p></div>
        <div className="account-order-actions"><strong>{money(order.total, order.currency_code)}</strong><Link href={`/account/orders/${encodeURIComponent(order.id)}`} className="text-link">View order ↗</Link></div>
      </li>)}</ul> : !claimable.length && <p>Orders placed while signed in will appear here.</p>}
    {claimable.length > 0 && <div className="account-claimable">
      <h3>Link a recent guest order</h3>
      <p>These new guest orders match your verified sign-in email. Linking adds them to your account without changing the original order details.</p>
      <ul className="account-order-list">{claimable.map((order) => <li key={order.id}>
        <div><strong>{orderLabel(order)}</strong><p>{order.created_at ? new Date(order.created_at).toLocaleDateString("en-ZA") : "Date unavailable"} · {order.status}</p></div>
        <Button type="button" className="account-secondary" disabled={Boolean(busyId)} onClick={() => void claim(order.id)}>{busyId === order.id ? "Linking…" : "Link order"}</Button>
      </li>)}</ul>
    </div>}
    {!loading && hasMore && <div className="account-actions"><Button type="button" className="account-secondary" disabled={Boolean(busyId)} onClick={() => void loadMore()}>Load more orders</Button></div>}
    {error && (orders.length > 0 || claimable.length > 0) && <p role="alert" className="account-error">{error}</p>}
  </section>;
}
