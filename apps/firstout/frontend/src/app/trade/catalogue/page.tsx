"use client";

import { Button, InlineNotification, NumberInput, Stack, Theme } from "@carbon/react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import {
  ApiError,
  formatZarAmount,
  getPortalMe,
  listPortalCatalogue,
  placePortalOrder,
  portalLogout,
  type PortalCatalogueItem,
  type PortalMe,
} from "@/lib/api";

export default function TradeCataloguePage() {
  const router = useRouter();
  const [me, setMe] = useState<PortalMe | null>(null);
  const [items, setItems] = useState<PortalCatalogueItem[]>([]);
  const [qty, setQty] = useState<Record<string, number>>({});
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  useEffect(() => {
    void getPortalMe()
      .then(async (user) => {
        setMe(user);
        setItems(await listPortalCatalogue());
      })
      .catch(() => router.replace("/trade/login"));
  }, [router]);

  if (!me) {
    return null;
  }

  return (
    <Theme theme="g10">
      <main style={{ maxWidth: "48rem", margin: "2rem auto", padding: "1rem" }}>
        <Stack gap={5}>
          <div style={{ display: "flex", justifyContent: "space-between" }}>
            <h1>Catalogue — {me.customer_name}</h1>
            <Button
              kind="ghost"
              onClick={() =>
                void portalLogout().then(() => router.replace("/trade/login"))
              }
            >
              Sign out
            </Button>
          </div>
          {error ? <InlineNotification kind="error" title={error} hideCloseButton /> : null}
          {success ? <InlineNotification kind="success" title={success} hideCloseButton /> : null}
          {items.map((item) => (
            <div key={item.id} style={{ display: "flex", gap: "1rem", alignItems: "end" }}>
              <div style={{ flex: 1 }}>
                <strong>{item.our_ref}</strong> {item.name}
                <div>{formatZarAmount(item.unit_inc_vat)} inc VAT</div>
              </div>
              <NumberInput
                id={`qty-${item.id}`}
                label="Qty"
                min={1}
                value={qty[item.id] ?? 1}
                onChange={(_, { value }) =>
                  setQty((current) => ({ ...current, [item.id]: value === "" ? 1 : Number(value) }))
                }
              />
              <Button
                size="sm"
                onClick={() => {
                  setError(null);
                  void placePortalOrder({
                    lines: [{ sku_id: item.id, qty: qty[item.id] ?? 1 }],
                  })
                    .then((order) => setSuccess(`Draft order ${order.so_number} placed`))
                    .catch((err) =>
                      setError(err instanceof ApiError ? err.message : "Could not place order"),
                    );
                }}
              >
                Order
              </Button>
            </div>
          ))}
        </Stack>
      </main>
    </Theme>
  );
}
