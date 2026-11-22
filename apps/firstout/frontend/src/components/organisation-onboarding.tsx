"use client";

import { LoadingField, LoadingRegion, PageLoading } from "@/components/page-loading";

import { useAuth as useClerkAuth, useClerk } from "@clerk/nextjs";
import { ArrowRight, Enterprise } from "@carbon/icons-react";
import { Button, InlineNotification, SkeletonText, Stack, Tab, TabList, TabPanel, TabPanels, Tabs, Tile } from "@carbon/react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { OrganisationForm } from "./organisation-form";
import { activateWorkspace } from "@/lib/workspace-activation";
import { createOrganisation, getSignupIdentity, getSignupStatus, organisationDestination, tenantSubdomainsEnabled, type CreateOrganisation, type Organisation } from "@/lib/organisations";
import { usePageError } from "@/hooks/use-page-error";

export function OrganisationOnboarding() {
  const { isLoaded, isSignedIn } = useClerkAuth();
  const clerk = useClerk();
  const [submitting, setSubmitting] = useState(false);
  const [created, setCreated] = useState<Organisation | null>(null);
  const [selectedTab, setSelectedTab] = useState(0);
  const [openingId, setOpeningId] = useState<string | null>(null);
  const createTab = useRef<HTMLElement>(null);
  const signup = useQuery({
    queryKey: ["signup"],
    queryFn: async () => {
      const [identity, status] = await Promise.all([getSignupIdentity(), getSignupStatus()]);
      return { identity, status };
    },
    enabled: Boolean(isLoaded && isSignedIn),
  });
  const identity = signup.data?.identity ?? null;
  const status = signup.data?.status ?? null;
  const loading = signup.isPending || signup.isFetching;
  const { error, setError } = usePageError(signup.error, "Unable to load your organisations.");

  async function openOrganisation(organisation: Organisation, settings = false) {
    setSubmitting(true);
    setOpeningId(organisation.id);
    setError(null);
    try {
      const destination = organisationDestination(organisation.slug, window.location.host, settings ? "/organisation" : "/");
      await activateWorkspace(clerk, organisation.clerk_org_id, destination);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to open this organisation. Try again.");
      setSubmitting(false);
      setOpeningId(null);
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

  if (!isLoaded) return <PageLoading kind="status" label="Loading sign-in…" />;
  if (!isSignedIn) return <Stack gap={5}>
    <p>Sign in and finish any required verification before opening or creating a business.</p>
    <Link className="cds--btn cds--btn--primary" href="/clerk-login">Continue sign-in</Link>
    <Link className="cds--link" href="/sign-up">New here? Create your account</Link>
  </Stack>;
  if (loading) return (
    <LoadingRegion label="Loading your organisations…">
      <Stack gap={7}>
        <div className="firstout-onboarding-account">
          <Stack gap={2} orientation="horizontal">
            <span className="firstout-onboarding-account-label">Signed in as</span>
            <SkeletonText width="9rem" />
          </Stack>
          <LoadingField width="5rem" height="2rem" />
        </div>
        <Tabs selectedIndex={0}>
          <TabList aria-label="Business workspaces" className="firstout-onboarding-tabs">
            <Tab>Your businesses</Tab>
            <Tab disabled>Create business</Tab>
          </TabList>
          <TabPanels>
            <TabPanel className="firstout-onboarding-panel">
              <Stack gap={5}>
                <p className="cds--type-body-01 firstout-onboarding-description">Choose a business to open its workspace.</p>
                <div className="firstout-organisation-workspaces" aria-hidden="true">
                  {["first", "second"].map((slot) => (
                    <Tile className="firstout-business-card" key={slot}>
                      <article>
                        <div className="firstout-business-card-heading">
                          <Enterprise size={24} />
                          <SkeletonText heading width="9rem" />
                        </div>
                        {tenantSubdomainsEnabled && <SkeletonText width="12rem" />}
                        <LoadingField width="10rem" height="3rem" />
                      </article>
                    </Tile>
                  ))}
                </div>
              </Stack>
            </TabPanel>
            <TabPanel />
          </TabPanels>
        </Tabs>
      </Stack>
    </LoadingRegion>
  );

  return <Stack gap={7}>
    <div className="firstout-onboarding-account">
      <p className="cds--type-body-01">{identity ? <><span className="firstout-onboarding-account-label">Signed in as</span> {identity.email}</> : "Signed in"}</p>
      <Button kind="ghost" size="sm" disabled={submitting} onClick={() => void clerk.signOut({ redirectUrl: "/clerk-login" })}>Sign out</Button>
    </div>
    {error ? <InlineNotification kind="error" title="We couldn’t finish that" subtitle={error} hideCloseButton lowContrast /> : null}
    {!identity ? <Button kind="secondary" onClick={() => void signup.refetch()}>Try again</Button> : <>
      {created ? <Tile><Stack gap={4}>
        <h2 className="cds--type-productive-heading-03">{created.name} is created</h2>
        <p>Your business is ready. Continue to add your logo and invite staff.</p>
        <Button disabled={submitting} onClick={() => void openOrganisation(created, true)}>Open organisation settings</Button>
      </Stack></Tile> : <Tabs selectedIndex={selectedTab} onChange={({ selectedIndex }) => setSelectedTab(selectedIndex)}>
        <TabList aria-label="Business workspaces" className="firstout-onboarding-tabs">
          <Tab disabled={submitting}>Your businesses</Tab>
          <Tab ref={createTab} disabled={submitting}>Create business</Tab>
        </TabList>
        <TabPanels>
          <TabPanel className="firstout-onboarding-panel">
            {identity.organisations.length > 0 ? <Stack gap={5}>
              <p className="cds--type-body-01 firstout-onboarding-description">Choose a business to open its workspace.</p>
              <div className="firstout-organisation-workspaces">{identity.organisations.map((organisation) => <Tile className="firstout-business-card" key={organisation.id}>
                <article aria-labelledby={`business-${organisation.id}`}>
                  <div className="firstout-business-card-heading">
                    <Enterprise size={24} aria-hidden="true" />
                    <h2 id={`business-${organisation.id}`} className="cds--type-productive-heading-02">{organisation.name}</h2>
                  </div>
                  {tenantSubdomainsEnabled ? <p className="cds--type-body-01 firstout-business-address">{organisation.slug}.app.firstout.co.za</p> : null}
                  <Button renderIcon={ArrowRight} disabled={submitting} onClick={() => void openOrganisation(organisation)}>
                    {openingId === organisation.id ? "Opening workspace…" : "Open workspace"}
                  </Button>
                </article>
              </Tile>)}</div>
            </Stack> : <Tile className="firstout-onboarding-empty"><Stack gap={5}>
              <Enterprise size={32} aria-hidden="true" />
              <Stack gap={3}>
                <h2 className="cds--type-productive-heading-02">No businesses yet</h2>
                <p className="cds--type-body-01">Create your first business to get started. If you’re joining an existing team, ask its owner for an invitation.</p>
              </Stack>
              <Button kind="tertiary" onClick={() => { setSelectedTab(1); createTab.current?.focus(); }}>Create a business</Button>
            </Stack></Tile>}
          </TabPanel>
          <TabPanel className="firstout-onboarding-panel">
            <div className="firstout-onboarding-create"><Stack gap={6}>
              <Stack gap={3}>
                <h2 className="cds--type-productive-heading-03">Set up a new business</h2>
                <p className="cds--type-body-01 firstout-onboarding-description">Give your business its own workspace. You can add your team and finish the details later.</p>
              </Stack>
              {status?.enabled ? <OrganisationForm submitting={submitting} onSubmit={create} /> : <InlineNotification kind="info" title="New organisation signup is unavailable" subtitle="You can still open an existing organisation. Please try again later to create one." hideCloseButton lowContrast />}
            </Stack></div>
          </TabPanel>
        </TabPanels>
      </Tabs>}
    </>}
  </Stack>;
}
