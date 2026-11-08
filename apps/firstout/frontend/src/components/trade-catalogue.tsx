"use client";

import { Button, InlineNotification, Loading, NumberInput, Stack } from "@carbon/react";
import { useEffect, useState } from "react";
import {
  ApiError, formatZarAmount, getPortalMe, listPortalCatalogue, placePortalOrder,
  type PortalAccess, type PortalCatalogueItem, type PortalMe,
} from "@/lib/api";

/** The parent remounts this entire workspace whenever the approved access changes. */
export function TradeCatalogue({ access }: { access: PortalAccess }) {
  const [me, setMe] = useState<PortalMe | null>(null);
  const [items, setItems] = useState<PortalCatalogueItem[]>([]);
  const [qty, setQty] = useState<Record<string, number>>({});
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    Promise.all([getPortalMe(access.id), listPortalCatalogue(access.id)])
      .then(([user, catalogue]) => { if (!cancelled) { setMe(user); setItems(catalogue); } })
      .catch((err: unknown) => { if (!cancelled) setError(err instanceof Error ? err.message : "Could not load this catalogue."); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [access.id]);

  async function order(itemId: string) {
    setBusy(itemId); setError(null); setSuccess(null);
    try {
      const order = await placePortalOrder(access.id, { lines: [{ sku_id: itemId, qty: qty[itemId] ?? 1 }] });
      setSuccess(`Draft order ${order.so_number} placed. Staff will confirm it.`);
    } catch (err) {
      if (err instanceof ApiError && (err.status === 401 || err.status === 403)) {
        setMe(null); setItems([]); setQty({});
      }
      setError(err instanceof Error ? err.message : "Could not place order.");
    } finally { setBusy(null); }
  }

  return <Stack gap={5}>
    <h2 className="cds--type-productive-heading-03">{access.organisation_name} — {access.customer_name}</h2>
    {error ? <InlineNotification kind="error" title="Trade catalogue" subtitle={error} hideCloseButton /> : null}
    {success ? <InlineNotification kind="success" title="Order placed" subtitle={success} hideCloseButton /> : null}
    {loading ? <Loading withOverlay={false} description="Loading catalogue…" /> : me ? <>
      {!items.length ? <p>No SKUs available.</p> : items.map((item) => <div key={item.id} className="firstout-trade-item">
        <div><strong>{item.our_ref}</strong> {item.name}<div>{formatZarAmount(item.unit_ex_vat)} excl. VAT</div></div>
        <NumberInput id={`qty-${item.id}`} label="Qty" min={1} value={qty[item.id] ?? 1} disabled={busy !== null}
          onChange={(_, { value }) => setQty((current) => ({ ...current, [item.id]: value === "" ? 1 : Number(value) }))} />
        <Button size="sm" disabled={busy !== null || (qty[item.id] ?? 1) < 1} onClick={() => void order(item.id)}>{busy === item.id ? "Ordering…" : "Order"}</Button>
      </div>)}
    </> : null}
  </Stack>;
}
