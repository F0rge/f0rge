"use client";

import { ArrowRight, Building, Location as LocationIcon, UserFollow, InventoryManagement } from "@carbon/icons-react";
import { Button, InlineNotification, Stack, Tile } from "@carbon/react";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { AdminDirectoryLinks, AdminPageHeader } from "@/components/administration";
import { PageLoading } from "@/components/page-loading";
import { StaffInvitationComposer } from "@/components/staff-invitation-composer";
import { StaffMetrics } from "@/components/staff-metrics";
import { isActiveLocation, listLocations, listRoles } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { ADMIN_DESTINATIONS, adminDestination, canOpenAdminDestination } from "@/lib/admin-navigation";
import { getCurrentOrganisation, getOrganisationInvitations } from "@/lib/organisations";
import { adminError, getStaffCapacity } from "@/lib/staff-administration";
import styles from "./organisation.module.css";

type Result<T> = { data: T; error?: never } | { data?: never; error: string };

function useOverviewData<T>(load: () => Promise<T>, attempt: number) {
  const [result, setResult] = useState<Result<T>>();
  useEffect(() => {
    let cancelled = false;
    load().then(
      (data) => { if (!cancelled) setResult({ data }); },
      (reason: unknown) => {
        if (!cancelled) setResult({ error: adminError(reason, "Could not load details.") });
      },
    );
    return () => { cancelled = true; };
  }, [attempt, load]);
  return result;
}

const loadActiveLocations = () => listLocations().then((items) => items.filter(isActiveLocation));

function OverviewError({ title, error, onRetry }: { title: string; error: string; onRetry: () => void }) {
  return (
    <Stack gap={3}>
      <InlineNotification kind="error" title={title} subtitle={error} hideCloseButton lowContrast />
      <Button kind="tertiary" size="sm" onClick={onRetry}>Try again</Button>
    </Stack>
  );
}

function OrganisationOverview() {
  const [overviewAttempt, setOverviewAttempt] = useState(0);
  const [staffAttempt, setStaffAttempt] = useState(0);
  const [placesAttempt, setPlacesAttempt] = useState(0);
  const [inviting, setInviting] = useState(false);
  const [notice, setNotice] = useState("");
  const inviteButton = useRef<HTMLButtonElement>(null);
  const organisation = useOverviewData(getCurrentOrganisation, overviewAttempt);
  const locations = useOverviewData(loadActiveLocations, placesAttempt);
  const capacity = useOverviewData(getStaffCapacity, staffAttempt);
  const roles = useOverviewData(listRoles, staffAttempt);
  const invitations = useOverviewData(getOrganisationInvitations, staffAttempt);
  const { label, description } = ADMIN_DESTINATIONS.organisation;

  function closeInvitation() {
    setInviting(false);
    requestAnimationFrame(() => inviteButton.current?.focus());
  }

  function refreshStaff() {
    setStaffAttempt((value) => value + 1);
  }

  return (
    <Stack gap={6}>
      <AdminPageHeader title={label} description={description}>
        {organisation?.data ? (
          <Button ref={inviteButton} renderIcon={UserFollow} aria-expanded={inviting} onClick={() => setInviting(true)}>
            Invite staff
          </Button>
        ) : null}
      </AdminPageHeader>
      {organisation?.error ? (
        <OverviewError title="Organisation unavailable" error={organisation.error} onRetry={() => setOverviewAttempt((value) => value + 1)} />
      ) : !organisation?.data ? (
        <PageLoading kind="status" label="Loading organisation…" />
      ) : (
        <>
          {notice && <InlineNotification kind="success" title={notice} onCloseButtonClick={() => setNotice("")} lowContrast />}
          {inviting && (
            <>
              {roles?.error || invitations?.error ? (
                <OverviewError title="Invitation details unavailable" error={roles?.error ?? invitations?.error ?? "Could not load invitation details."} onRetry={refreshStaff} />
              ) : null}
              <StaffInvitationComposer
                roles={roles?.data ?? []}
                capacity={capacity?.data ?? null}
                invitations={invitations?.data ?? null}
                onInvited={(invitation) => {
                  setNotice(`Invitation sent to ${invitation.email}.`);
                  closeInvitation();
                  refreshStaff();
                }}
                onRefresh={refreshStaff}
                onCancel={closeInvitation}
              />
            </>
          )}
          <Tile className={styles.summary}>
            <span className={styles.symbol}><Building size={28} aria-hidden="true" /></span>
            <div>
              <h2 className="cds--type-heading-04">{organisation.data.name}</h2>
              <p>Workspace address · {organisation.data.slug}</p>
            </div>
            <Link className={`cds--link ${styles.trailing}`} href={adminDestination("company").href}>Company details <ArrowRight size={16} aria-hidden="true" /></Link>
          </Tile>
          {capacity?.error ? (
            <OverviewError title="Staff capacity unavailable" error={capacity.error} onRetry={refreshStaff} />
          ) : <StaffMetrics capacity={capacity?.data} />}
          <Stack gap={4}>
            <div className={styles.row}>
              <h2 className="cds--type-heading-03">Administration directory</h2>
              <Link className="cds--link" href="/users?tab=invitations">Review invitations <ArrowRight size={16} aria-hidden="true" /></Link>
            </div>
            <AdminDirectoryLinks items={["team", "roles", "settings", "audit", "profile"]} />
          </Stack>
          <Tile className={styles.places}>
            <Stack gap={4}>
              <div className={styles.row}>
                <div>
                  <h2 className="cds--type-heading-03">Operating locations</h2>
                  <p>Active showrooms and warehouses in this organisation.</p>
                </div>
                <Link className="cds--link" href={adminDestination("locations").href}>Location defaults <ArrowRight size={16} aria-hidden="true" /></Link>
              </div>
              {locations?.error ? (
                <OverviewError title="Locations unavailable" error={locations.error} onRetry={() => setPlacesAttempt((value) => value + 1)} />
              ) : !locations?.data ? (
                <PageLoading kind="status" label="Loading locations…" />
              ) : locations.data.length ? (
                <ul className={styles.placeList}>
                  {locations.data.map((location) => {
                    const Icon = location.type === "warehouse" ? InventoryManagement : LocationIcon;
                    return (
                      <li key={location.id}>
                        <Icon size={20} aria-hidden="true" />
                        <div><strong>{location.name}</strong><span>{location.type === "warehouse" ? "Warehouse" : "Showroom"}</span></div>
                      </li>
                    );
                  })}
                </ul>
              ) : <p>No active locations.</p>}
              <Link className="cds--link" href="/locations">Manage locations <ArrowRight size={16} aria-hidden="true" /></Link>
            </Stack>
          </Tile>
          <Link className="cds--link" href="/onboarding">Create another organisation <ArrowRight size={16} aria-hidden="true" /></Link>
        </>
      )}
    </Stack>
  );
}

export default function OrganisationPage() {
  const { user } = useAuth();
  if (canOpenAdminDestination("organisation", user)) return <OrganisationOverview />;
  return (
    <Stack gap={6}>
      <AdminPageHeader title="Organisation" description={ADMIN_DESTINATIONS.organisation.description} />
      <InlineNotification kind="info" title="Owner access required" subtitle="The organisation overview is available to the workspace owner." hideCloseButton lowContrast />
    </Stack>
  );
}
