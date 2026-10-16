"use client";

import { InlineNotification, Stack, Tile } from "@carbon/react";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import {
  PurchaseHistoryTable,
  SupplierPricesTable,
} from "@/components/records/history-tables";
import { PartyRecords } from "@/components/records/party-records";
import { getSupplier, type Supplier } from "@/lib/api";
import { useAuth } from "@/lib/auth";

export default function SupplierDetailPage() {
  const params = useParams<{ id: string }>();
  const { user } = useAuth();
  const [supplier, setSupplier] = useState<Supplier | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!user) {
      return;
    }
    let cancelled = false;
    void getSupplier(params.id)
      .then((found) => {
        if (!cancelled) {
          setSupplier(found ?? null);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load supplier.");
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [user, params.id]);

  if (loading) {
    return <p className="cds--type-body-01">Loading…</p>;
  }

  if (error || !supplier) {
    return (
      <InlineNotification
        kind="error"
        title="Not found"
        subtitle={error ?? "This supplier could not be loaded."}
        hideCloseButton
        lowContrast
      />
    );
  }

  return (
    <Stack gap={6}>
      <Tile>
        <h1 className="cds--type-productive-heading-04">{supplier.name}</h1>
        <p className="cds--type-body-01">Default currency {supplier.default_currency}</p>
      </Tile>
      <PartyRecords kind="suppliers" id={supplier.id} />
      <SupplierPricesTable supplierId={supplier.id} />
      <PurchaseHistoryTable supplierId={supplier.id} />
    </Stack>
  );
}
