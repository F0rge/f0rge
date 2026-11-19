"use client";

import { Email, UserFollow } from "@carbon/icons-react";
import { Button, InlineNotification, Layer, Select, SelectItem, TextInput, Tile } from "@carbon/react";
import { useEffect, useId, useRef, useState, type FormEvent } from "react";
import { useAdminDraftNavigation } from "@/components/admin-save-actions";
import type { Role } from "@/lib/api";
import { inviteOrganisationMember, type OrganisationInvitation } from "@/lib/organisations";
import {
  adminError, availableStaffPlaces, invitationRoleSummary, staffInvitationFor, type StaffCapacity,
} from "@/lib/staff-administration";
import styles from "./staff-invitation-composer.module.css";

export function StaffInvitationComposer({
  roles, capacity, invitations, onInvited, onCancel, onRefresh,
}: {
  roles: readonly Role[];
  capacity: StaffCapacity | null;
  invitations: readonly OrganisationInvitation[] | null;
  onInvited: (invitation: OrganisationInvitation) => void;
  onCancel: () => void;
  onRefresh: () => void;
}) {
  const headingId = useId();
  const emailId = useId();
  const roleId = useId();
  const emailInput = useRef<HTMLInputElement>(null);
  const inFlight = useRef(false);
  const [email, setEmail] = useState("");
  const [emailTouched, setEmailTouched] = useState(false);
  const [validEmail, setValidEmail] = useState(false);
  const [role, setRole] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const selected = roles.find((item) => item.slug === role);
  const matchingInvite = staffInvitationFor(invitations ?? [], email);
  // A pending approval with uncertain Clerk delivery is retriable using the
  // original role, even when it already reserved the final place.
  const retry = matchingInvite?.delivery_confirmed === false && matchingInvite.role === role;
  const duplicate = matchingInvite && !retry
    ? matchingInvite.delivery_confirmed === false
      ? "Choose the role on the pending invitation to retry delivery."
      : "This email already has a pending invitation."
    : null;
  const emailError = emailTouched && email && !validEmail ? "Enter a full email address." : duplicate;
  useAdminDraftNavigation(Boolean(email || role), busy, "Discard this unfinished invitation?");
  const full = capacity !== null && availableStaffPlaces(capacity) === 0;
  const ready = capacity !== null && invitations !== null && roles.length > 0;

  useEffect(() => {
    emailInput.current?.focus();
  }, []);

  async function invite(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (inFlight.current || !ready || (full && !retry) || !validEmail || !selected || duplicate) return;
    inFlight.current = true;
    setBusy(true);
    setError(null);
    try {
      onInvited(await inviteOrganisationMember({ email: email.trim(), role }));
    } catch (reason) {
      setError(adminError(reason, "Could not send the invitation."));
      onRefresh();
    } finally {
      inFlight.current = false;
      setBusy(false);
    }
  }

  return (
    <Layer>
      <Tile className={styles.composer}>
        <section aria-labelledby={headingId}>
          <h2 className={styles.heading} id={headingId}><UserFollow size={20} aria-hidden="true" /> Invite a team member</h2>
          {error && <InlineNotification lowContrast kind="error" title="Could not send invitation" subtitle={error} hideCloseButton />}
          {!ready && <p className={styles.message} role="status">Invitation details must load before you can send.</p>}
          {full && !retry && (
            <InlineNotification lowContrast kind="info" title="All staff places are allocated"
              subtitle="Clerk memberships and pending invitations reserve places. Revoking a pending invitation can free a place." hideCloseButton />
          )}
          <Layer>
            <form className={styles.form} onSubmit={(event) => void invite(event)}>
              <div className={styles.fields}>
                <TextInput
                  id={emailId}
                  ref={emailInput}
                  labelText="Staff email"
                  type="email"
                  autoComplete="email"
                  value={email}
                  required
                  disabled={busy}
                  invalid={!!emailError}
                  invalidText={emailError}
                  onBlur={() => setEmailTouched(true)}
                  onChange={(event) => {
                    setEmail(event.target.value);
                    setValidEmail(event.target.validity.valid);
                    setError(null);
                  }}
                />
                <Select
                  id={roleId}
                  labelText="Organisation role"
                  value={role}
                  disabled={busy}
                  required
                  onChange={(event) => { setRole(event.target.value); setError(null); }}
                >
                  <SelectItem value="" text="Choose a role" />
                  {roles.map((item) => <SelectItem key={item.id} value={item.slug} text={item.name} />)}
                </Select>
              </div>
              <div aria-live="polite" className={selected ? undefined : "firstout-sr-only"}>
                {selected && (
                  <p className={styles.permissions}>
                    <strong>{selected.name} access</strong> · {invitationRoleSummary(selected)}
                  </p>
                )}
              </div>
              <div className={styles.actions}>
                <Button size="md" kind="tertiary" disabled={busy} onClick={onCancel}>Cancel</Button>
                <Button size="md" type="submit" renderIcon={Email}
                  disabled={!ready || (full && !retry) || busy || !validEmail || !selected || !!duplicate}>
                  {busy ? "Sending…" : retry ? "Retry invitation" : "Send invitation"}
                </Button>
              </div>
            </form>
          </Layer>
        </section>
      </Tile>
    </Layer>
  );
}
