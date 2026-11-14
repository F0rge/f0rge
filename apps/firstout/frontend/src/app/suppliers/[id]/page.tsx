"use client";

import { Button, InlineNotification, Stack, Tag, Tile } from "@carbon/react";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import {
  PurchaseHistoryTable,
  SupplierPricesTable,
} from "@/components/records/history-tables";
import { PartyRecords } from "@/components/records/party-records";
import { PartyArchiveAction } from "@/components/party-archive-actions";
import { canMutateCatalogue, getSupplier, setSupplierArchived, type Supplier } from "@/lib/api";
import { useAuth } from "@/lib/auth";

export default function SupplierDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const { user } = useAuth();
  const [supplier, setSupplier] = useState<Supplier | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const requestId = useRef(0);

  const loadSupplier = useCallback(async () => {
    const request = ++requestId.current;
    setLoading(true);setSupplier(null);setError(null);setSuccess(null);
    try {
      const found = await getSupplier(params.id);
      if (request === requestId.current) setSupplier(found);
    } catch (err) {
      if (request === requestId.current) setError(err instanceof Error ? err.message : "Failed to load supplier.");
    } finally {
      if (request === requestId.current) setLoading(false);
    }
  }, [params.id]);

  useEffect(() => {
    if (user) void loadSupplier();
    return () => { requestId.current += 1; };
  }, [user, loadSupplier]);

  if (loading || (supplier !== null && supplier.id !== params.id)) {
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
      <div className="firstout-page-header">
        <div>
          <Button kind="ghost" size="sm" onClick={() => router.push(`/suppliers${supplier.is_archived ? "?archived=true" : ""}`)}>Back to suppliers</Button>
          <h1 className="cds--type-productive-heading-04">{supplier.name}</h1>
          {supplier.is_archived ? <Tag type="gray">Archived</Tag> : null}
        </div>
        {canMutateCatalogue(user) ? <PartyArchiveAction
          key={supplier.id}
          kind="supplier"
          name={supplier.name}
          archived={supplier.is_archived}
          onConfirm={async () => {
            const request = requestId.current;
            const updated = await setSupplierArchived(supplier.id, !supplier.is_archived);
            if (request !== requestId.current) return;
            setSupplier(updated);
            setSuccess(updated.is_archived ? "Supplier archived. Account details and history are preserved." : "Supplier restored to the active list.");
          }}
        /> : null}
      </div>
      {success ? <InlineNotification kind="success" title="Saved" subtitle={success} onCloseButtonClick={() => setSuccess(null)} lowContrast /> : null}
      {supplier.is_archived ? <InlineNotification kind="info" title="This supplier is archived" subtitle="Contacts, terms and purchasing history are preserved. Restore the account before using it in new transactions." hideCloseButton lowContrast /> : null}
      <Tile>
        <h2 className="cds--type-productive-heading-03">Account</h2>
        <p className="cds--type-body-01">Default currency {supplier.default_currency}</p>
      </Tile>
      <PartyRecords kind="suppliers" id={supplier.id} />
      <SupplierPricesTable supplierId={supplier.id} />
      <PurchaseHistoryTable supplierId={supplier.id} />
    </Stack>
  );
}
