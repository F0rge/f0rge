"use client";

import { Button, InlineNotification, Loading, Stack, Tile } from "@carbon/react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { getSettings, listRoles, type AppSettings, type Role } from "@/lib/api";
import { getCurrentOrganisation, getOrganisationInvitations, type CurrentOrganisation, type OrganisationInvitation } from "@/lib/organisations";
import { OrganisationDetails } from "@/components/organisation-details";
import { OrganisationInvitations } from "@/components/organisation-invitations";

type PageData = { organisation: CurrentOrganisation; settings: AppSettings; roles: Role[]; invitations: OrganisationInvitation[] };

export default function OrganisationPage() {
  const [data, setData] = useState<PageData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const organisation = await getCurrentOrganisation();
        if (organisation.role !== "owner") throw new Error("Only an organisation owner can configure this workspace. Ask your owner for changes.");
        const [settings, roles, invitations] = await Promise.all([getSettings(), listRoles(), getOrganisationInvitations()]);
        if (!cancelled) { setData({ organisation, settings, roles, invitations }); setError(null); }
      } catch (reason) { if (!cancelled) setError(reason instanceof Error ? reason.message : "Unable to load organisation settings."); }
      finally { if (!cancelled) setLoading(false); }
    }
    void load();
    return () => { cancelled = true; };
  }, [attempt]);

  if (loading) return <Loading withOverlay={false} description="Loading organisation settings…" />;
  return <Stack gap={7}>
    <header className="firstout-page-header"><div>
      <h1 className="cds--type-productive-heading-04">Organisation</h1>
      <p className="cds--type-body-01">Configure your business and invite staff.</p>
    </div><Link href="/onboarding" className="cds--link">Create another organisation</Link></header>
    {error ? <><InlineNotification kind="error" title="Organisation settings unavailable" subtitle={error} hideCloseButton lowContrast />
      <Button kind="secondary" onClick={() => { setLoading(true); setAttempt((value) => value + 1); }}>Try again</Button></> : null}
    {data ? <div className="firstout-organisation-content"><Stack gap={7}>
      <Tile><Stack gap={3}><h2 className="cds--type-productive-heading-03">{data.organisation.name}</h2><p>{data.organisation.slug}</p>
        <p>Free plan · up to {data.organisation.max_members} staff members.</p></Stack></Tile>
      <OrganisationDetails initial={data.settings} />
      <hr />
      <OrganisationInvitations organisation={data.organisation} roles={data.roles} initialInvitations={data.invitations} />
      <hr />
      <div className="firstout-organisation-links"><Link href="/locations" className="cds--link">Manage locations</Link><Link href="/users" className="cds--link">Manage existing staff</Link><Link href="/settings" className="cds--link">All settings and label preferences</Link></div>
    </Stack></div> : null}
  </Stack>;
}
