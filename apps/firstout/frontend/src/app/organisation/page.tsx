"use client";

import { ArrowRight, Building, Location as LocationIcon, UserFollow, InventoryManagement } from "@carbon/icons-react";
import { Button, InlineNotification, Stack, Tile } from "@carbon/react";
import Link from "next/link";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { AdminDirectoryLinks, AdminPageHeader } from "@/components/administration";
import { PageLoading } from "@/components/page-loading";
import { StaffInvitationComposer } from "@/components/staff-invitation-composer";
import { StaffMetrics } from "@/components/staff-metrics";
import { isActiveLocation, listRoles, type Location } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { referenceQueries } from "@/lib/queries";
import { ADMIN_DESTINATIONS, adminDestination, canOpenAdminDestination } from "@/lib/admin-navigation";
import { getCurrentOrganisation, getOrganisationInvitations } from "@/lib/organisations";
import { adminError, getStaffCapacity } from "@/lib/staff-administration";
import styles from "./organisation.module.css";

const activeLocations = (items: Location[]) => items.filter(isActiveLocation);
const DETAILS_ERROR = "Could not load details.";
const STAFF_KEYS = [["staff-capacity"], ["staff-roles"], ["staff-invitations"]];

function OverviewError({ title, error, onRetry }: { title: string; error: string; onRetry: () => void }) {
  return (
    <Stack gap={3}>
      <InlineNotification kind="error" title={title} subtitle={error} hideCloseButton lowContrast />
      <Button kind="tertiary" size="sm" onClick={onRetry}>Try again</Button>
    </Stack>
  );
}

function OrganisationOverview() {
  const [inviting, setInviting] = useState(false);
  const [notice, setNotice] = useState("");
  const inviteButton = useRef<HTMLButtonElement>(null);
  const client = useQueryClient();
  const organisation = useQuery({ queryKey: ["organisation"], queryFn: getCurrentOrganisation });
  const locations = useQuery({ ...referenceQueries.locations, select: activeLocations });
  const capacity = useQuery({ queryKey: ["staff-capacity"], queryFn: getStaffCapacity });
  const roles = useQuery({ queryKey: ["staff-roles"], queryFn: listRoles });
  const invitations = useQuery({ queryKey: ["staff-invitations"], queryFn: getOrganisationInvitations });
  const { label, description } = ADMIN_DESTINATIONS.organisation;

  function closeInvitation() {
    setInviting(false);
    requestAnimationFrame(() => inviteButton.current?.focus());
  }

  function refreshStaff() {
    for (const queryKey of STAFF_KEYS) void client.invalidateQueries({ queryKey });
  }

  return (
    <Stack gap={6}>
      <AdminPageHeader title={label} description={description}>
        {organisation.data ? (
          <Button ref={inviteButton} renderIcon={UserFollow} aria-expanded={inviting} onClick={() => setInviting(true)}>
            Invite staff
          </Button>
        ) : null}
      </AdminPageHeader>
      {organisation.error ? (
        <OverviewError title="Organisation unavailable" error={adminError(organisation.error, DETAILS_ERROR)} onRetry={() => void organisation.refetch()} />
      ) : !organisation.data ? (
        <PageLoading kind="status" label="Loading organisation…" />
      ) : (
        <>
          {notice && <InlineNotification kind="success" title={notice} onCloseButtonClick={() => setNotice("")} lowContrast />}
          {inviting && (
            <>
              {roles.error || invitations.error ? (
                <OverviewError title="Invitation details unavailable" error={adminError(roles.error ?? invitations.error, DETAILS_ERROR)} onRetry={refreshStaff} />
              ) : null}
              <StaffInvitationComposer
                roles={roles.data ?? []}
                capacity={capacity.data ?? null}
                invitations={invitations.data ?? null}
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
          {capacity.error ? (
            <OverviewError title="Staff capacity unavailable" error={adminError(capacity.error, DETAILS_ERROR)} onRetry={refreshStaff} />
          ) : <StaffMetrics capacity={capacity.data} />}
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
              {locations.error ? (
                <OverviewError title="Locations unavailable" error={adminError(locations.error, DETAILS_ERROR)} onRetry={() => void locations.refetch()} />
              ) : !locations.data ? (
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
