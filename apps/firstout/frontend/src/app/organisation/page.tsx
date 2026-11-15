"use client";

import {
  Button,
  InlineNotification,
  ProgressBar,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableHeader,
  TableRow,
  Tag,
  Tile,
} from "@carbon/react";
import { ArrowRight, Building, UserMultiple } from "@carbon/icons-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import {
  getSettings,
  isActiveLocation,
  listLocations,
  listRoles,
  type AppSettings,
  type Location,
  type Role,
} from "@/lib/api";
import {
  getCurrentOrganisation,
  getOrganisationInvitations,
  type CurrentOrganisation,
  type OrganisationInvitation,
} from "@/lib/organisations";
import { OrganisationDetails } from "@/components/organisation-details";
import { OrganisationInvitations } from "@/components/organisation-invitations";
import { PageLoading } from "@/components/page-loading";
import styles from "./organisation.module.css";

type PageData = {
  organisation: CurrentOrganisation;
  settings: AppSettings;
  roles: Role[];
  invitations: OrganisationInvitation[];
};

export default function OrganisationPage() {
  const [data, setData] = useState<PageData | null>(null);
  const [locations, setLocations] = useState<Location[]>([]);
  const [locationsError, setLocationsError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const organisation = await getCurrentOrganisation();
        if (organisation.role !== "owner")
          throw new Error(
            "Only an organisation owner can configure this workspace. Ask your owner for changes.",
          );
        const [settings, roles, invitations] = await Promise.all([
          getSettings(),
          listRoles(),
          getOrganisationInvitations(),
        ]);
        if (!cancelled) {
          setData({ organisation, settings, roles, invitations });
          setError(null);
        }
        // Locations enhance the overview; a location failure must not hide business or invitation settings.
        try {
          const result = await listLocations();
          if (!cancelled) {
            setLocations(result);
            setLocationsError(null);
          }
        } catch (reason) {
          if (!cancelled)
            setLocationsError(
              reason instanceof Error
                ? reason.message
                : "Unable to load locations.",
            );
        }
      } catch (reason) {
        if (!cancelled) {
          setData(null);
          setError(
            reason instanceof Error
              ? reason.message
              : "Unable to load organisation settings.",
          );
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [attempt]);

  const pending =
    data?.invitations.filter((invitation) => invitation.status === "pending")
      .length ?? 0;
  const allocated = (data?.organisation.member_count ?? 0) + pending;
  const activeLocations = locations.filter(isActiveLocation);

  if (loading)
    return (
      <PageLoading kind="organisation" label="Loading organisation settings…" />
    );
  return (
    <Stack gap={7} className={styles.workspace}>
      <header className="firstout-page-header">
        <div>
          <h1 className="cds--type-heading-05">Organisation</h1>
          <p className="cds--type-body-01">
            Configure your business, locations and team.
          </p>
        </div>
        <Link href="/onboarding" className="cds--link">
          Create another organisation
        </Link>
      </header>
      {error ? (
        <>
          <InlineNotification
            kind="error"
            title="Organisation settings unavailable"
            subtitle={error}
            hideCloseButton
            lowContrast
          />
          <Button
            kind="secondary"
            onClick={() => {
              setLoading(true);
              setAttempt((value) => value + 1);
            }}
          >
            Try again
          </Button>
        </>
      ) : null}
      {data ? (
        <>
          <div
            className={`${styles.intro} firstout-tone-info firstout-section-accent`}
          >
            <Building size={32} aria-hidden="true" />
            <div>
              <h2 className="cds--type-heading-03">
                Your business, connected.
              </h2>
              <p className="cds--type-body-01">
                Keep your identity, places and people together.
              </p>
            </div>
            <Tag type="gray">Owner workspace</Tag>
          </div>
          <OrganisationDetails initial={data.settings}>
            <Tile>
              <Stack gap={5}>
                <div className={styles.headingRow}>
                  <Building size={32} aria-hidden="true" />
                  <Tag type="gray">Free plan</Tag>
                </div>
                <h2 className="cds--type-heading-04">
                  {data.organisation.name}
                </h2>
                <p className="cds--type-label-01 firstout-muted-text">
                  Organisation slug: {data.organisation.slug}
                </p>
                <ProgressBar
                  label="Staff places allocated"
                  value={allocated}
                  max={data.organisation.max_members}
                  helperText={`${data.organisation.member_count} members + ${pending} pending invitations · ${allocated} of ${data.organisation.max_members} places`}
                />
                <p className="cds--type-helper-text-01">
                  Only the organisation owner can change these details. Pending
                  invitations reserve a staff place.
                </p>
                <Link href="/settings" className="cds--link">
                  All settings and label preferences
                </Link>
              </Stack>
            </Tile>
          </OrganisationDetails>
          <Stack gap={5}>
            <div className={styles.headingRow}>
              <div>
                <h2 className="cds--type-heading-03">Locations</h2>
                <p className="cds--type-body-01 firstout-muted-text">
                  Warehouses and showrooms where your team receives, stores and
                  sells stock.
                </p>
              </div>
              <Button
                as={Link}
                href="/locations"
                kind="tertiary"
                renderIcon={ArrowRight}
              >
                Manage locations
              </Button>
            </div>
            {locationsError ? (
              <InlineNotification
                kind="error"
                title="Locations unavailable"
                subtitle={locationsError}
                hideCloseButton
                lowContrast
              />
            ) : (
              <TableContainer
                title={`${activeLocations.length} active ${activeLocations.length === 1 ? "location" : "locations"}`}
                description="Manage locations to add, rename, archive or restore places and configure bins and labels."
              >
                <div className={styles.tableScroll}>
                  <Table aria-label="Organisation locations">
                    <TableHead>
                      <TableRow>
                        <TableHeader>Location</TableHeader>
                        <TableHeader>Type</TableHeader>
                        <TableHeader>Status</TableHeader>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {locations.map((location) => (
                        <TableRow key={location.id}>
                          <TableCell>
                            <Link href="/locations" className="cds--link">
                              {location.name}
                            </Link>
                          </TableCell>
                          <TableCell>
                            <Tag type="gray">
                              {location.type === "warehouse"
                                ? "Warehouse"
                                : "Showroom"}
                            </Tag>
                          </TableCell>
                          <TableCell>
                            <Tag
                              type={
                                location.is_archived ? "warm-gray" : "green"
                              }
                            >
                              {location.is_archived ? "Archived" : "Active"}
                            </Tag>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
                {locations.length === 0 ? (
                  <p className={styles.entry}>
                    No locations yet. Add your first warehouse or showroom in
                    Manage locations.
                  </p>
                ) : null}
              </TableContainer>
            )}
          </Stack>
          <Tile>
            <div className={styles.entry}>
              <UserMultiple size={32} aria-hidden="true" />
              <div>
                <h2 className="cds--type-heading-03">Existing staff</h2>
                <p className="cds--type-body-01 firstout-muted-text">
                  Review roles, default locations and enabled access.
                </p>
              </div>
              <Button
                as={Link}
                href="/users"
                kind="tertiary"
                renderIcon={ArrowRight}
              >
                Manage existing staff
              </Button>
            </div>
          </Tile>
          <OrganisationInvitations
            organisation={data.organisation}
            roles={data.roles}
            initialInvitations={data.invitations}
            onInvitationsChange={(invitations) =>
              setData((current) =>
                current ? { ...current, invitations } : current,
              )
            }
          />
        </>
      ) : null}
    </Stack>
  );
}
