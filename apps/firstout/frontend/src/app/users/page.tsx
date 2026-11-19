"use client";

import { UserFollow } from "@carbon/icons-react";
import {
  Button, InlineNotification, Stack, Tab, TabList, TabPanel, TabPanels, Tabs,
} from "@carbon/react";
import { QueryClient, QueryClientProvider, useQuery, useQueryClient } from "@tanstack/react-query";
import { useSearchParams } from "next/navigation";
import { Suspense, useRef, useState } from "react";
import { AdminPageHeader } from "@/components/administration";
import { PageLoading } from "@/components/page-loading";
import { StaffMetrics } from "@/components/staff-metrics";
import { StaffInvitationComposer } from "@/components/staff-invitation-composer";
import { can, listLocations, listRoles, type AuthUser } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { getOrganisationInvitations, type OrganisationInvitation } from "@/lib/organisations";
import { workspaceIdentity } from "@/lib/record-workspace";
import { adminError, getStaffCapacity, isOwnerRole } from "@/lib/staff-administration";
import { StaffInvitations } from "./staff-invitations";
import { StaffMembers } from "./staff-members";
import styles from "./users.module.css";

function UsersScreen({ user }: { user: AuthUser }) {
  const params = useSearchParams();
  const [tab, setTab] = useState(params.get("tab") === "invitations" ? 1 : 0);
  const [inviting, setInviting] = useState(params.get("invite") === "1");
  const [notice, setNotice] = useState("");
  const launcher = useRef<HTMLButtonElement>(null);
  const client = useQueryClient();
  const capacity = useQuery({ queryKey: ["staff-capacity"], queryFn: getStaffCapacity });
  const invitations = useQuery({ queryKey: ["staff-invitations"], queryFn: getOrganisationInvitations });
  const roles = useQuery({ queryKey: ["staff-roles"], queryFn: listRoles });
  const locations = useQuery({ queryKey: ["staff-locations"], queryFn: listLocations });
  const roleOptions = roles.data ?? [];
  const locationOptions = locations.data ?? [];
  const actorIsOwner = isOwnerRole(user.role, roleOptions);

  const refreshInvitations = () => {
    void client.invalidateQueries({ queryKey: ["staff-capacity"] });
    void client.invalidateQueries({ queryKey: ["staff-invitations"] });
  };

  function closeInvitation() {
    setInviting(false);
    requestAnimationFrame(() => launcher.current?.focus());
  }

  function onInvited(invitation: OrganisationInvitation) {
    client.setQueryData<OrganisationInvitation[]>(["staff-invitations"], (previous = []) => [
      invitation, ...previous.filter((item) => item.id !== invitation.id),
    ]);
    setTab(1);
    setNotice("Invitation sent to " + invitation.email + ".");
    closeInvitation();
    refreshInvitations();
  }

  return (
    <Stack gap={5} className={styles.page}>
      <AdminPageHeader
        title="Team members"
        description={"Manage the people who can access " + user.team.name + " and the roles they hold."}
      >
        <Button ref={launcher} renderIcon={UserFollow} aria-expanded={inviting} onClick={() => setInviting(true)}>
          Invite staff
        </Button>
      </AdminPageHeader>
      {capacity.error && !capacity.data ? (
        <div className={styles.feedback}>
          <InlineNotification lowContrast kind="error" title="Staff capacity is unavailable" subtitle={adminError(capacity.error, "Could not load staff capacity.")} hideCloseButton />
          <Button kind="tertiary" size="sm" onClick={() => void capacity.refetch()} disabled={capacity.isFetching}>Retry capacity</Button>
        </div>
      ) : <StaffMetrics capacity={capacity.data} />}
      {notice && <InlineNotification lowContrast kind="success" title={notice} onCloseButtonClick={() => setNotice("")} />}
      {inviting && <>
        {roles.error && !roles.data && (
          <div className={styles.feedback}>
            <InlineNotification lowContrast kind="error" title="Invitation roles are unavailable" subtitle={adminError(roles.error, "Could not load roles.")} hideCloseButton />
            <Button kind="tertiary" size="sm" disabled={roles.isFetching} onClick={() => void roles.refetch()}>Retry roles</Button>
          </div>
        )}
        <StaffInvitationComposer
          roles={roleOptions.filter((item) => actorIsOwner || !isOwnerRole(item.slug, roleOptions))}
          capacity={capacity.data ?? null}
          invitations={invitations.data ?? null}
          onInvited={onInvited}
          onCancel={closeInvitation}
          onRefresh={refreshInvitations}
        />
        {invitations.error && !invitations.data && (
          <Button kind="tertiary" size="sm" onClick={refreshInvitations} disabled={invitations.isFetching}>Retry invitation details</Button>
        )}
      </>}
      <section aria-labelledby="staff-directory-title" className={styles.directory}>
        <h2 id="staff-directory-title" className={styles.sectionTitle}>Staff directory</h2>
        <Tabs selectedIndex={tab} onChange={({ selectedIndex }) => setTab(selectedIndex)}>
          <TabList aria-label="Staff directory views" className={styles.tabList}>
            <Tab>Members</Tab>
            <Tab>{invitations.data ? "Invitations (" + invitations.data.length + ")" : "Invitations"}</Tab>
          </TabList>
          <TabPanels>
            <TabPanel className={styles.tabPanel}>
              <StaffMembers
                user={user}
                roles={roleOptions}
                locations={locationOptions}
                optionsReady={roles.isSuccess && locations.isSuccess}
                optionsError={roles.error ?? locations.error}
                retryOptions={() => { void roles.refetch(); void locations.refetch(); }}
                onChanged={() => void client.invalidateQueries({ queryKey: ["staff-capacity"] })}
              />
            </TabPanel>
            <TabPanel className={styles.tabPanel}>
              <StaffInvitations
                invitations={invitations.data}
                error={invitations.error}
                loading={invitations.isPending}
                refresh={refreshInvitations}
                canRevoke={(item) => actorIsOwner || (roles.isSuccess && !isOwnerRole(item.role, roleOptions))}
                onRevoked={(item) => {
                  client.setQueryData<OrganisationInvitation[]>(["staff-invitations"], (previous) =>
                    previous?.map((row) => row.id === item.id ? { ...row, status: "revoked" } : row),
                  );
                  setNotice("Invitation to " + item.email + " revoked.");
                  refreshInvitations();
                }}
                roleName={(slug) => roleOptions.find((item) => item.slug === slug)?.name ?? slug}
              />
            </TabPanel>
          </TabPanels>
        </Tabs>
      </section>
    </Stack>
  );
}

function UsersDirectory({ user }: { user: AuthUser }) {
  const [client] = useState(() => new QueryClient({
    defaultOptions: { queries: { retry: false, refetchOnWindowFocus: false } },
  }));
  return (
    <QueryClientProvider client={client}>
      <Suspense fallback={<PageLoading label="Loading team members…" />}>
        <UsersScreen user={user} />
      </Suspense>
    </QueryClientProvider>
  );
}

export default function UsersPage() {
  const { user, loading } = useAuth();
  if (loading) return <PageLoading label="Loading team members…" />;
  if (!user || !can(user, "users.manage")) {
    return <InlineNotification kind="error" title="Access denied" subtitle="Staff management permission is required." hideCloseButton />;
  }
  return <UsersDirectory key={workspaceIdentity(user)} user={user} />;
}
