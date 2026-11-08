"use client";

import { Button, InlineNotification, Stack, TextInput, Tile } from "@carbon/react";
import { useCallback, useEffect, useState } from "react";
import {
  createPortalInvitation, listCustomerPortalAccess, listPortalInvitations,
  revokeCustomerPortalAccess, revokePortalInvitation,
  type CreatedPortalInvitation, type CustomerPortalAccess, type PortalInvitation,
} from "@/lib/api";

export function CustomerPortalAccessPanel({ customerId, defaultEmail }: { customerId: string; defaultEmail: string }) {
  const [email, setEmail] = useState(defaultEmail);
  const [invitations, setInvitations] = useState<PortalInvitation[]>([]);
  const [access, setAccess] = useState<CustomerPortalAccess[]>([]);
  const [created, setCreated] = useState<CreatedPortalInvitation | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const load = useCallback(async () => {
    const [nextInvitations, nextAccess] = await Promise.all([
      listPortalInvitations(customerId), listCustomerPortalAccess(customerId),
    ]);
    setInvitations(nextInvitations);
    setAccess(nextAccess);
  }, [customerId]);

  useEffect(() => {
    let cancelled = false;
    Promise.all([listPortalInvitations(customerId), listCustomerPortalAccess(customerId)])
      .then(([nextInvitations, nextAccess]) => {
        if (!cancelled) { setInvitations(nextInvitations); setAccess(nextAccess); }
      })
      .catch((err: unknown) => { if (!cancelled) setError(err instanceof Error ? err.message : "Could not load trade access."); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [customerId]);

  async function create() {
    setBusy(true); setError(null); setCreated(null); setCopied(false);
    try {
      setCreated(await createPortalInvitation(customerId, email.trim()));
      await load();
    } catch (err) { setError(err instanceof Error ? err.message : "Could not create invitation."); }
    finally { setBusy(false); }
  }

  async function revoke(kind: "invitation" | "access", id: string) {
    setBusy(true); setError(null);
    try {
      if (kind === "invitation") {
        await revokePortalInvitation(customerId, id);
        if (created?.id === id) setCreated(null);
      } else await revokeCustomerPortalAccess(customerId, id);
      await load();
    } catch (err) { setError(err instanceof Error ? err.message : "Could not revoke trade access."); }
    finally { setBusy(false); }
  }

  async function copy() {
    if (!created) return;
    try { await navigator.clipboard.writeText(created.invitation_url); setCopied(true); }
    catch { setError("Could not copy. Select the invitation link and copy it manually."); }
  }

  return <Tile><Stack gap={5}>
    <h2 className="cds--type-productive-heading-03">Trade portal access</h2>
    <p className="cds--type-body-01">Invite a customer to sign in with Clerk. They can browse their catalogue and place draft orders; staff still confirm orders.</p>
    {error ? <InlineNotification kind="error" title="Trade access" subtitle={error} hideCloseButton /> : null}
    <TextInput id="portal-invitation-email" type="email" labelText="Customer sign-in email" value={email} onChange={(event) => setEmail(event.target.value)} disabled={busy} />
    <Button kind="secondary" disabled={busy || !email.trim()} onClick={() => void create()}>{busy ? "Working…" : "Create invitation link"}</Button>
    {created ? <Stack gap={3}>
      <TextInput id="portal-invitation-link" labelText="Invitation link" value={created.invitation_url} readOnly helperText={`Share this link with ${created.email}. Expires ${new Date(created.expires_at).toLocaleString()}. The link is shown only now and is not emailed automatically.`} />
      <Button kind="tertiary" onClick={() => void copy()}>{copied ? "Copied" : "Copy invitation link"}</Button>
    </Stack> : null}
    {loading ? <p>Loading trade access…</p> : <>
      <h3 className="cds--type-productive-heading-02">Invitations</h3>
      {!invitations.length ? <p>No invitations.</p> : invitations.map((entry) => <div key={entry.id} className="firstout-catalogue-actions">
        <span>{entry.email} · {entry.status} · expires {new Date(entry.expires_at).toLocaleString()}</span>
        {entry.status === "pending" ? <Button kind="danger--ghost" size="sm" disabled={busy} onClick={() => void revoke("invitation", entry.id)}>Revoke invitation</Button> : null}
      </div>)}
      <h3 className="cds--type-productive-heading-02">Customer accounts</h3>
      {!access.length ? <p>No accepted customer accounts.</p> : access.map((entry) => <div key={entry.id} className="firstout-catalogue-actions">
        <span>{entry.email} · {entry.status}</span>
        {entry.status === "active" ? <Button kind="danger--ghost" size="sm" disabled={busy} onClick={() => void revoke("access", entry.id)}>Revoke access</Button> : null}
      </div>)}
    </>}
  </Stack></Tile>;
}
