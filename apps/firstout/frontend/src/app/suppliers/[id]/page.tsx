"use client";

import { LoadingRegion } from "@/components/page-loading";
import { Button, InlineNotification, SkeletonText, Stack, Tag, Tile } from "@carbon/react";
import { useParams, useRouter } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import {
  PartyHistoryLoading,
  PurchaseHistoryTable,
  SupplierPricesTable,
} from "@/components/records/history-tables";
import { PartyRecords, PartyRecordsLoading } from "@/components/records/party-records";
import { PartyArchiveAction } from "@/components/party-archive-actions";
import { canMutateCatalogue, getSupplier, setSupplierArchived } from "@/lib/api";
import { useAuth } from "@/lib/auth";

export default function SupplierDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const { user } = useAuth();
  const client = useQueryClient();
  const supplierQuery = useQuery({ queryKey: ["suppliers", { id: params.id }], queryFn: () => getSupplier(params.id), enabled: Boolean(user) });
  const supplier = supplierQuery.data ?? null;
  const loading = supplierQuery.isPending;
  const error = supplierQuery.error ? supplierQuery.error.message || "Failed to load supplier." : null;
  // A notice belongs to the supplier it was raised on.
  const [notice, setNotice] = useState<{ id: string; text: string } | null>(null);
  const success = notice?.id === params.id ? notice.text : null;
  const setSuccess = (text: string | null) => setNotice(text ? { id: params.id, text } : null);

  if (loading || (supplier !== null && supplier.id !== params.id)) {
    return (
      <Stack gap={6} className="firstout-loading-motion">
        <div>
          <Button kind="ghost" size="sm" onClick={() => router.push("/suppliers")}>Back to suppliers</Button>
          <SkeletonText heading width="min(22rem, 85%)" />
        </div>
        <LoadingRegion label="Loading supplier…">
          <Stack gap={6}>
            <Tile>
              <h2 className="cds--type-productive-heading-03">Account</h2>
              <Stack gap={2} orientation="horizontal">
                <span className="cds--type-body-01">Default currency</span>
                <SkeletonText width="3rem" />
              </Stack>
            </Tile>
            <PartyRecordsLoading announce={false} />
            <PartyHistoryLoading type="prices" />
            <PartyHistoryLoading type="purchases" />
          </Stack>
        </LoadingRegion>
      </Stack>
    );
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
            const updated = await setSupplierArchived(supplier.id, !supplier.is_archived);
            client.setQueryData(["suppliers", { id: updated.id }], updated);
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
