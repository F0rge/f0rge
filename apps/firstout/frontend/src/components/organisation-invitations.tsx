"use client";

import {
  Button,
  InlineNotification,
  Modal,
  Select,
  SelectItem,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableHeader,
  TableRow,
  Tag,
  TextInput,
  Tile,
} from "@carbon/react";
import { useState, type FormEvent } from "react";
import type { Role } from "@/lib/api";
import {
  getOrganisationInvitations,
  inviteOrganisationMember,
  organisationInvitesFull,
  revokeOrganisationInvitation,
  type CurrentOrganisation,
  type OrganisationInvitation,
} from "@/lib/organisations";
import styles from "@/app/organisation/organisation.module.css";

type Props = {
  organisation: CurrentOrganisation;
  roles: Role[];
  initialInvitations: OrganisationInvitation[];
  onInvitationsChange?: (invitations: OrganisationInvitation[]) => void;
};

export function OrganisationInvitations({
  organisation,
  roles,
  initialInvitations,
  onInvitationsChange,
}: Props) {
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("");
  const [invitations, setInvitations] = useState(initialInvitations);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [confirmRevoke, setConfirmRevoke] =
    useState<OrganisationInvitation | null>(null);
  const full = organisationInvitesFull(organisation, invitations);
  const placesAvailable = Math.max(
    0,
    organisation.max_members -
      organisation.member_count -
      invitations.filter((item) => item.status === "pending").length,
  );

  function applyInvitations(next: OrganisationInvitation[]) {
    setInvitations(next);
    onInvitationsChange?.(next);
  }

  async function refresh() {
    try {
      applyInvitations(await getOrganisationInvitations());
    } catch (reason) {
      setError(
        `The change was saved, but the invitation list could not be refreshed. ${reason instanceof Error ? reason.message : "Reload this page to check the latest status."}`,
      );
    }
  }

  async function invite(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy || !email.trim() || !role || full) return;
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const invited = await inviteOrganisationMember({
        email: email.trim(),
        role,
      });
      applyInvitations([
        ...invitations.filter((item) => item.id !== invited.id),
        invited,
      ]);
      setEmail("");
      setNotice(`Invitation sent to ${invited.email}.`);
      await refresh();
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "Unable to send the invitation.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function revoke(invitation: OrganisationInvitation) {
    if (busy) return;
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      await revokeOrganisationInvitation(invitation.id);
      applyInvitations(
        invitations.map((item) =>
          item.id === invitation.id ? { ...item, status: "revoked" } : item,
        ),
      );
      setConfirmRevoke(null);
      setNotice(`Invitation to ${invitation.email} revoked.`);
      await refresh();
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "Unable to revoke the invitation.",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <Stack gap={5}>
      <Tile>
        <Stack gap={5}>
          <div className={styles.headingRow}>
            <h2 className="cds--type-heading-03">Invite your team</h2>
            <Tag type={full ? "warm-gray" : "green"}>
              {placesAvailable} {placesAvailable === 1 ? "place" : "places"}{" "}
              available
            </Tag>
          </div>
          <p className="cds--type-body-01">
            Give each person their own access. {organisation.member_count} of{" "}
            {organisation.max_members} staff places are in use. Pending
            invitations reserve a place.
          </p>
          {error ? (
            <InlineNotification
              kind="error"
              title="Invitations"
              subtitle={error}
              hideCloseButton
              lowContrast
            />
          ) : null}
          {notice ? (
            <InlineNotification
              kind="success"
              title={notice}
              hideCloseButton
              lowContrast
            />
          ) : null}
          {full ? (
            <InlineNotification
              kind="info"
              title="All staff places are allocated"
              subtitle="Revoke a pending invitation or manage existing staff before inviting another person."
              hideCloseButton
              lowContrast
            />
          ) : null}
          <form onSubmit={(event) => void invite(event)}>
            <Stack gap={5}>
              <div className={styles.businessGrid}>
                <TextInput
                  id="invitation-email"
                  labelText="Staff email"
                  type="email"
                  autoComplete="email"
                  value={email}
                  required
                  disabled={busy || full}
                  onChange={(event) => setEmail(event.target.value)}
                />
                <Select
                  id="invitation-role"
                  labelText="Role in this organisation"
                  value={role}
                  disabled={busy || full}
                  required
                  onChange={(event) => setRole(event.target.value)}
                >
                  <SelectItem value="" text="Choose a role" />
                  {roles.map((item) => (
                    <SelectItem
                      key={item.id}
                      value={item.slug}
                      text={item.name}
                    />
                  ))}
                </Select>
              </div>
              <Button
                type="submit"
                disabled={busy || full || !email.trim() || !role}
              >
                {busy ? "Working…" : "Send invitation"}
              </Button>
            </Stack>
          </form>
        </Stack>
      </Tile>
      <TableContainer
        title="Staff invitations"
        description="Review pending invitations and revoke access before an invitation is accepted."
      >
        <div className={styles.tableScroll}>
          <Table aria-label="Staff invitations">
            <TableHead>
              <TableRow>
                <TableHeader>Email</TableHeader>
                <TableHeader>Role</TableHeader>
                <TableHeader>Status</TableHeader>
                <TableHeader>Action</TableHeader>
              </TableRow>
            </TableHead>
            <TableBody>
              {invitations.map((item) => (
                <TableRow key={item.id}>
                  <TableCell>{item.email}</TableCell>
                  <TableCell>
                    <Tag type="gray">
                      {roles.find((entry) => entry.slug === item.role)?.name ??
                        item.role}
                    </Tag>
                  </TableCell>
                  <TableCell>
                    <Tag
                      type={
                        item.status === "pending"
                          ? "purple"
                          : item.status === "accepted"
                            ? "green"
                            : "gray"
                      }
                    >
                      {item.status}
                    </Tag>
                  </TableCell>
                  <TableCell>
                    {item.status === "pending" ? (
                      <Button
                        kind="ghost"
                        size="sm"
                        disabled={busy}
                        onClick={() => setConfirmRevoke(item)}
                        aria-label={`Revoke invitation to ${item.email}`}
                      >
                        Revoke
                      </Button>
                    ) : (
                      "—"
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
        {invitations.length === 0 ? (
          <p className={styles.entry}>
            No invitations yet. Invite a staff member to get started.
          </p>
        ) : null}
      </TableContainer>
      <Modal
        open={confirmRevoke !== null}
        modalHeading="Revoke invitation?"
        modalLabel="Staff access"
        primaryButtonText={busy ? "Revoking…" : "Revoke invitation"}
        secondaryButtonText="Keep invitation"
        danger
        primaryButtonDisabled={busy}
        preventCloseOnClickOutside
        onRequestClose={() => {
          if (!busy) setConfirmRevoke(null);
        }}
        onRequestSubmit={() => {
          if (confirmRevoke) void revoke(confirmRevoke);
        }}
        onSecondarySubmit={() => {
          if (!busy) setConfirmRevoke(null);
        }}
      >
        <p>
          Revoke the invitation to {confirmRevoke?.email}? They will no longer
          be able to accept this invitation.
        </p>
        {error ? (
          <InlineNotification
            kind="error"
            title="Invitation could not be revoked"
            subtitle={error}
            hideCloseButton
            lowContrast
          />
        ) : null}
      </Modal>
    </Stack>
  );
}
