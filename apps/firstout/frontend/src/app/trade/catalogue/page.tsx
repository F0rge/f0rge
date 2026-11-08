"use client";

import { Button, InlineNotification, Loading, Select, SelectItem, Stack } from "@carbon/react";
import { useAuth as useClerkAuth } from "@clerk/nextjs";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { listPortalOrganisations, type PortalAccess } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { portalAccessUrl, tradeAuthUrl } from "@/lib/trade-auth";
import { ClerkAccountButton } from "@/components/clerk-account-button";
import { TradeCatalogue } from "@/components/trade-catalogue";

function TradePortal() {
  const { isLoaded, isSignedIn } = useClerkAuth();
  const { logout } = useAuth();
  const router = useRouter();
  const search = useSearchParams();
  const requestedAccess = search.get("access");
  const [access, setAccess] = useState<PortalAccess[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isLoaded || !isSignedIn) return;
    let cancelled = false;
    listPortalOrganisations()
      .then((data) => { if (!cancelled) setAccess(data); })
      .catch((err: unknown) => { if (!cancelled) setError(err instanceof Error ? err.message : "Could not load trade accounts."); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [isLoaded, isSignedIn]);

  if (!isLoaded) return <Loading withOverlay={false} description="Loading sign-in…" />;
  if (!isSignedIn) return <main className="firstout-onboarding-page"><Stack gap={5}>
    <h1 className="cds--type-productive-heading-04">Trade portal</h1>
    <p>Sign in with your Clerk account to open your approved trade accounts.</p>
    <Button href={tradeAuthUrl("login", requestedAccess ? portalAccessUrl(requestedAccess) : "/trade/catalogue")}>Sign in</Button>
  </Stack></main>;
  const selected = requestedAccess ? access.find((entry) => entry.id === requestedAccess) : access.length === 1 ? access[0] : undefined;
  return <main className="firstout-trade-page"><Stack gap={6}>
    <div className="firstout-page-header">
      <h1 className="cds--type-productive-heading-04">Trade portal</h1>
      <div className="firstout-catalogue-actions">
        <ClerkAccountButton />
        <Button kind="ghost" onClick={() => void logout().then(() => router.replace("/trade/login"))}>Sign out</Button>
      </div>
    </div>
    {error ? <InlineNotification kind="error" title="Trade accounts" subtitle={error} hideCloseButton /> : null}
    {loading ? <Loading withOverlay={false} description="Loading trade accounts…" /> : <>
      {access.length ? <Select id="trade-account" labelText="Business and customer account" value={selected?.id ?? ""} onChange={(event) => router.push(event.target.value ? portalAccessUrl(event.target.value) : "/trade/catalogue")}>
        <SelectItem value="" text="Choose an approved account" />
        {access.map((entry) => <SelectItem key={entry.id} value={entry.id} text={`${entry.organisation_name} — ${entry.customer_name}`} />)}
      </Select> : <p>No trade access has been approved for this account. Ask the business for an invitation link and open it using the invited email.</p>}
      {requestedAccess && !selected ? <InlineNotification kind="error" title="Account unavailable" subtitle="This trade account is not available to your sign-in. Choose an approved account." hideCloseButton /> : null}
      {selected ? <TradeCatalogue key={selected.id} access={selected} /> : null}
    </>}
  </Stack></main>;
}

export default function TradeCataloguePage() {
  return <Suspense fallback={<p>Loading trade portal…</p>}><TradePortal /></Suspense>;
}
