"use client";

import { LoadingField, LoadingRegion } from "@/components/page-loading";

import { Button, InlineNotification, NumberInput, SkeletonText, Stack } from "@carbon/react";
import { useEffect, useState } from "react";
import {
  ApiError, formatZarAmount, getPortalMe, listPortalCatalogue, placePortalOrder,
  type PortalAccess, type PortalCatalogueItem, type PortalMe,
} from "@/lib/api";
import {
  quantityInputBounds, quantityRuleHelper, quantityRuleRefusal, startQty, type QuantityRuleRefusal,
} from "@/lib/sale-quantity-rule";

/** The parent remounts this entire workspace whenever the approved access changes. */
export function TradeCatalogue({ access }: { access: PortalAccess }) {
  const [me, setMe] = useState<PortalMe | null>(null);
  const [items, setItems] = useState<PortalCatalogueItem[]>([]);
  const [qty, setQty] = useState<Record<string, number>>({});
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [refusal, setRefusal] = useState<QuantityRuleRefusal | null>(null);

  useEffect(() => {
    let cancelled = false;
    Promise.all([getPortalMe(access.id), listPortalCatalogue(access.id)])
      .then(([user, catalogue]) => { if (!cancelled) { setMe(user); setItems(catalogue); } })
      .catch((err: unknown) => { if (!cancelled) setError(err instanceof Error ? err.message : "Could not load this catalogue."); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [access.id]);

  // A batch-sold piece starts at its minimum; the portal has no authority to break a batch.
  const qtyFor = (item: PortalCatalogueItem) => qty[item.id] ?? startQty(item);

  async function order(item: PortalCatalogueItem) {
    const itemId = item.id;
    setBusy(itemId); setError(null); setSuccess(null); setRefusal(null);
    try {
      const order = await placePortalOrder(access.id, { lines: [{ sku_id: itemId, qty: qtyFor(item) }] });
      setSuccess(`Draft order ${order.so_number} placed. Staff will confirm it.`);
    } catch (err) {
      if (err instanceof ApiError && (err.status === 401 || err.status === 403)) {
        setMe(null); setItems([]); setQty({});
      }
      // A batch-sold piece: the message belongs to that item, not the page.
      const rule = quantityRuleRefusal(err);
      if (rule) setRefusal(rule);
      else setError(err instanceof Error ? err.message : "Could not place order.");
    } finally { setBusy(null); }
  }

  return <Stack gap={5}>
    <h2 className="cds--type-productive-heading-03">{access.organisation_name} — {access.customer_name}</h2>
    {error ? <InlineNotification kind="error" title="Trade catalogue" subtitle={error} hideCloseButton /> : null}
    {success ? <InlineNotification kind="success" title="Order placed" subtitle={success} hideCloseButton /> : null}
    {loading ? (
      <LoadingRegion label="Loading trade catalogue…">
        <Stack gap={5}>
          {["first", "second", "third"].map((row) => (
            <div key={row} className="firstout-trade-item">
              <div aria-hidden="true"><SkeletonText paragraph lineCount={2} width="65%" /></div>
              <LoadingField label="Qty" />
              <LoadingField width="5rem" height="2rem" />
            </div>
          ))}
        </Stack>
      </LoadingRegion>
    ) : me ? <>
      {!items.length ? <p>No SKUs available.</p> : items.map((item) => <div key={item.id} className="firstout-trade-item">
        <div><strong>{item.our_ref}</strong> {item.name}<div>{formatZarAmount(item.unit_ex_vat)} excl. VAT</div></div>
        <NumberInput id={`qty-${item.id}`} label="Qty" {...quantityInputBounds(item, false)} value={qtyFor(item)}
          disabled={busy !== null} helperText={quantityRuleHelper(item) ?? undefined}
          invalid={refusal?.lines[item.id]?.qty === qtyFor(item)} invalidText={refusal?.lines[item.id]?.message}
          onChange={(_, { value }) => setQty((current) => ({ ...current, [item.id]: value === "" ? startQty(item) : Number(value) }))} />
        <Button size="sm" disabled={busy !== null || qtyFor(item) < 1} onClick={() => void order(item)}>{busy === item.id ? "Ordering…" : "Order"}</Button>
      </div>)}
    </> : null}
  </Stack>;
}
