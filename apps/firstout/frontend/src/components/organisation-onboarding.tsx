"use client";

import { useAuth as useClerkAuth, useClerk } from "@clerk/nextjs";
import { Button, InlineNotification, Loading, Stack, Tile } from "@carbon/react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { OrganisationForm } from "./organisation-form";
import { createOrganisation, getSignupIdentity, getSignupStatus, organisationDestination, tenantSubdomainsEnabled, type CreateOrganisation, type Organisation, type SignupIdentity, type SignupStatus } from "@/lib/organisations";

export function OrganisationOnboarding() {
  const { isLoaded, isSignedIn } = useClerkAuth();
  const clerk = useClerk();
  const [identity, setIdentity] = useState<SignupIdentity | null>(null);
  const [status, setStatus] = useState<SignupStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [created, setCreated] = useState<Organisation | null>(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    if (!isLoaded || !isSignedIn) return;
    let cancelled = false;
    Promise.all([getSignupIdentity(), getSignupStatus()])
      .then(([who, available]) => { if (!cancelled) { setIdentity(who); setStatus(available); setError(null); } })
      .catch((reason: unknown) => { if (!cancelled) setError(reason instanceof Error ? reason.message : "Unable to load your organisations."); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [isLoaded, isSignedIn, attempt]);

  async function openOrganisation(organisation: Organisation, settings = false) {
    setSubmitting(true);
    setError(null);
    try {
      const destination = organisationDestination(organisation.slug, window.location.host, settings ? "/organisation" : "/");
      await clerk.setActive({
        organization: organisation.clerk_org_id,
        navigate: ({ decorateUrl }) => { window.location.assign(decorateUrl(destination)); },
      });
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to open this organisation. Try again.");
      setSubmitting(false);
    }
  }

  async function create(body: CreateOrganisation) {
    setSubmitting(true);
    setError(null);
    try {
      const organisation = await createOrganisation(body);
      setCreated(organisation);
      await openOrganisation(organisation, true);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to create your organisation. Try again.");
      setSubmitting(false);
    }
  }

  if (!isLoaded) return <Loading withOverlay={false} description="Loading sign-in…" />;
  if (!isSignedIn) return <Stack gap={5}>
    <p>Sign in and finish any required verification before opening or creating a business.</p>
    <Link className="cds--btn cds--btn--primary" href="/clerk-login">Continue sign-in</Link>
    <Link className="cds--link" href="/sign-up">New here? Create your account</Link>
  </Stack>;
  if (loading) return <Loading withOverlay={false} description="Loading your organisations…" />;

  return <Stack gap={7}>
    {error ? <InlineNotification kind="error" title="We couldn’t finish that" subtitle={error} hideCloseButton lowContrast /> : null}
    {!identity ? <Button kind="secondary" onClick={() => { setLoading(true); setAttempt((value) => value + 1); }}>Try again</Button> : <>
      <p className="cds--type-body-01">Signed in as {identity.email}.</p>
      {created ? <Tile><Stack gap={4}>
        <h2 className="cds--type-productive-heading-03">{created.name} is created</h2>
        <p>Your business is ready. Continue to add your logo and invite staff.</p>
        <Button disabled={submitting} onClick={() => void openOrganisation(created, true)}>Open organisation settings</Button>
      </Stack></Tile> : <>
        {identity.organisations.length > 0 ? <section><Stack gap={5}>
          <h2 className="cds--type-productive-heading-03">Your organisations</h2>
          <div className="firstout-organisation-workspaces">{identity.organisations.map((organisation) => <Tile key={organisation.id}>
            <Stack gap={4}><h3 className="cds--type-productive-heading-02">{organisation.name}</h3><p className="cds--type-body-01">{tenantSubdomainsEnabled ? `${organisation.slug}.app.firstout.co.za` : organisation.slug}</p>
              <Button kind="tertiary" disabled={submitting} onClick={() => void openOrganisation(organisation)}>Open workspace</Button>
            </Stack>
          </Tile>)}</div>
        </Stack></section> : null}
        <section><Stack gap={5}>
          <h2 className="cds--type-productive-heading-03">Set up a new business</h2>
          {status?.enabled ? <OrganisationForm submitting={submitting} onSubmit={create} /> : <InlineNotification kind="info" title="New organisation signup is unavailable" subtitle="You can still open an existing organisation. Please try again later to create one." hideCloseButton lowContrast />}
        </Stack></section>
      </>}
    </>}
    <Button kind="ghost" disabled={submitting} onClick={() => void clerk.signOut({ redirectUrl: "/clerk-login" })}>Sign out</Button>
  </Stack>;
}
