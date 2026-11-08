"use client";

import { Button, InlineNotification, Select, SelectItem, Stack, TextInput } from "@carbon/react";
import { useState, type FormEvent } from "react";
import type { Role } from "@/lib/api";
import { getOrganisationInvitations, inviteOrganisationMember, organisationInvitesFull, revokeOrganisationInvitation, type CurrentOrganisation, type OrganisationInvitation } from "@/lib/organisations";

type Props = { organisation: CurrentOrganisation; roles: Role[]; initialInvitations: OrganisationInvitation[] };

export function OrganisationInvitations({ organisation, roles, initialInvitations }: Props) {
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("");
  const [invitations, setInvitations] = useState(initialInvitations);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const full = organisationInvitesFull(organisation, invitations);

  async function invite(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!email.trim() || !role || full) return;
    setBusy(true); setError(null); setNotice(null);
    try {
      const invited = await inviteOrganisationMember({ email: email.trim(), role });
      setInvitations(await getOrganisationInvitations());
      setEmail(""); setNotice(`Invitation sent to ${invited.email}.`);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Unable to send the invitation."); }
    finally { setBusy(false); }
  }

  async function revoke(invitation: OrganisationInvitation) {
    setBusy(true); setError(null); setNotice(null);
    try {
      await revokeOrganisationInvitation(invitation.id);
      setInvitations(await getOrganisationInvitations());
      setNotice(`Invitation to ${invitation.email} revoked.`);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Unable to revoke the invitation."); }
    finally { setBusy(false); }
  }

  return <Stack gap={5}>
    <h2 className="cds--type-productive-heading-03">Invite your staff</h2>
    <p>{organisation.member_count} of {organisation.max_members} staff places are in use. Pending invitations reserve a place.</p>
    {error ? <InlineNotification kind="error" title="Invitation failed" subtitle={error} hideCloseButton lowContrast /> : null}
    {notice ? <InlineNotification kind="success" title={notice} hideCloseButton lowContrast /> : null}
    {full ? <InlineNotification kind="info" title="All staff places are allocated" subtitle="Revoke a pending invitation or manage existing staff before inviting another person." hideCloseButton lowContrast /> : null}
    <form onSubmit={(event) => void invite(event)}><Stack gap={5}>
      <div className="firstout-organisation-form-grid">
        <TextInput id="invitation-email" labelText="Staff email" type="email" autoComplete="email" value={email} required disabled={busy || full} onChange={(event) => setEmail(event.target.value)} />
        <Select id="invitation-role" labelText="Role in this organisation" value={role} disabled={busy || full} required onChange={(event) => setRole(event.target.value)}>
          <SelectItem value="" text="Choose a role" />
          {roles.map((item) => <SelectItem key={item.id} value={item.slug} text={item.name} />)}
        </Select>
      </div>
      <Button type="submit" disabled={busy || full || !email.trim() || !role}>{busy ? "Working…" : "Send invitation"}</Button>
    </Stack></form>
    {invitations.length > 0 ? <div className="firstout-organisation-table"><table className="cds--data-table">
      <caption className="cds--type-heading-compact-01">Staff invitations</caption>
      <thead><tr><th scope="col">Email</th><th scope="col">Role</th><th scope="col">Status</th><th scope="col">Action</th></tr></thead>
      <tbody>{invitations.map((item) => <tr key={item.id}><td>{item.email}</td><td>{roles.find((entry) => entry.slug === item.role)?.name ?? item.role}</td><td>{item.status}</td><td>
        {item.status === "pending" ? <Button kind="ghost" size="sm" disabled={busy} onClick={() => void revoke(item)} aria-label={`Revoke invitation to ${item.email}`}>Revoke</Button> : "—"}
      </td></tr>)}</tbody>
    </table></div> : <p>No invitations yet. Invite a staff member to get started.</p>}
  </Stack>;
}
