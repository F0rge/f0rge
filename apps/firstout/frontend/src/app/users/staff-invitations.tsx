"use client";

import {
  Button, InlineNotification, Modal, Search, Table, TableBody,
  TableCell, TableHead, TableHeader, TableRow, DataTableSkeleton, Tag,
} from "@carbon/react";
import { useCallback, useRef, useState } from "react";
import { revokeOrganisationInvitation, type OrganisationInvitation } from "@/lib/organisations";
import { adminError } from "@/lib/staff-administration";
import styles from "./users.module.css";

export function StaffInvitations({
  invitations, error, loading, refresh, canRevoke, onRevoked, roleName,
}: {
  invitations: OrganisationInvitation[] | undefined;
  error: Error | null;
  loading: boolean;
  refresh: () => void;
  canRevoke: (item: OrganisationInvitation) => boolean;
  onRevoked: (item: OrganisationInvitation) => void;
  roleName: (slug: string) => string;
}) {
  const [search, setSearch] = useState("");
  const [target, setTarget] = useState<OrganisationInvitation | null>(null);
  const inFlight = useRef(false);
  const [busy, setBusy] = useState(false);
  const [revokeError, setRevokeError] = useState("");
  const searchInput = useRef<HTMLInputElement>(null);
  const close = useCallback(() => {
    if (!inFlight.current) setTarget(null);
  }, []);

  async function revoke() {
    if (!target || !canRevoke(target) || inFlight.current) return;
    inFlight.current = true;
    setBusy(true);
    setRevokeError("");
    try {
      await revokeOrganisationInvitation(target.id);
      onRevoked(target);
      setTarget(null);
      requestAnimationFrame(() => searchInput.current?.focus());
    } catch (reason) {
      setRevokeError(adminError(reason, "Could not revoke the invitation."));
      refresh();
    } finally {
      inFlight.current = false;
      setBusy(false);
    }
  }

  const query = search.trim().toLowerCase();
  const rows = invitations?.filter((item) => [
    item.email, roleName(item.role), item.status,
  ].some((value) => value.toLowerCase().includes(query))) ?? [];
  return (
    <>
      <Search id="staff-invitations-search" ref={searchInput} labelText="Search invitations" placeholder="Search invitations" value={search} onChange={(event) => setSearch(event.target.value)} />
      {error && (
        <div className={styles.feedback}>
          <InlineNotification kind="error" title="Could not load invitations" subtitle={adminError(error, "Invitations are unavailable.")} hideCloseButton lowContrast />
          <Button size="sm" kind="tertiary" onClick={refresh}>Retry invitations</Button>
        </div>
      )}
      {loading ? (
        <DataTableSkeleton aria-label="Loading staff invitations" columnCount={4} rowCount={3} showHeader={false} showToolbar={false} />
      ) : rows.length > 0 ? (
        <div className={styles.tableScroll} tabIndex={0} role="region" aria-label="Staff invitations table">
          <Table size="lg" aria-label="Staff invitations">
            <TableHead>
              <TableRow>
                <TableHeader>Email</TableHeader>
                <TableHeader>Role</TableHeader>
                <TableHeader>Status</TableHeader>
                <TableHeader><span className="firstout-sr-only">Manage</span></TableHeader>
              </TableRow>
            </TableHead>
            <TableBody>
              {rows.map((item) => (
                <TableRow key={item.id}>
                  <TableCell className={styles.email}>{item.email}</TableCell>
                  <TableCell>{roleName(item.role)}</TableCell>
                  <TableCell>
                    <Tag size="sm" type={item.status === "pending" ? "purple" : item.status === "accepted" ? "green" : "gray"}>
                      {item.status === "pending" && item.delivery_confirmed === false
                        ? "Delivery unconfirmed"
                        : item.status[0].toUpperCase() + item.status.slice(1)}
                    </Tag>
                  </TableCell>
                  <TableCell>
                    {item.status === "pending" && canRevoke(item) && (
                      <Button
                        kind="danger--ghost" size="sm" aria-label={"Revoke invitation to " + item.email}
                        onClick={() => { setRevokeError(""); setTarget(item); }}
                      >Revoke</Button>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      ) : invitations && (
        <p role="status" className={styles.empty}>{query ? "No invitations match your search." : "No staff invitations yet."}</p>
      )}
      {target && (
        <Modal
          open danger size="sm" preventCloseOnClickOutside
          modalHeading="Revoke invitation?"
          primaryButtonText={busy ? "Revoking…" : "Revoke invitation"}
          secondaryButtonText="Keep invitation"
          primaryButtonDisabled={busy}
          onRequestSubmit={() => void revoke()}
          onRequestClose={close}
          onSecondarySubmit={close}
          selectorPrimaryFocus=".cds--btn--secondary"
        >
          <p>{target.email} will no longer be able to accept this invitation.</p>
          {revokeError && <InlineNotification kind="error" title="Could not revoke invitation" subtitle={revokeError} hideCloseButton lowContrast />}
        </Modal>
      )}
    </>
  );
}
