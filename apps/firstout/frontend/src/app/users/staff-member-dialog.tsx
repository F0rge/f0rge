"use client";

import { Button, InlineNotification, Modal, Select, SelectItem, Stack, Tag, TextInput } from "@carbon/react";
import { useCallback, useRef, useState, type FormEvent } from "react";
import { isActiveLocation, updateUser, type AuthUser, type Location, type Role, type User } from "@/lib/api";
import { userEditPayload, type UserEditForm } from "@/lib/user-edit";
import { adminError } from "@/lib/staff-administration";
import styles from "./users.module.css";

export type StaffMember = User & { can_edit_display_name?: boolean };
type View = "details" | "edit" | "status";

function editForm(member: StaffMember): UserEditForm {
  return {
    display_name: member.display_name ?? "",
    role: member.role,
    default_location_id: member.default_location_id ?? "",
  };
}

export function StaffMemberDialog({
  member, user, roles, roleName, locations, locationName, editable, onClose, onChanged,
}: {
  member: StaffMember;
  user: AuthUser;
  roles: Role[];
  roleName: (slug: string) => string;
  locations: Location[];
  locationName: (id: string | null) => string;
  editable: boolean;
  onClose: () => void;
  onChanged: (user: StaffMember, message: string) => void;
}) {
  const [view, setView] = useState<View>("details");
  const [form, setForm] = useState(() => editForm(member));
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const inFlight = useRef(false);
  const close = useRef(onClose);
  const formRef = useRef<HTMLFormElement>(null);
  const self = user.id === member.id;
  const canEditName = member.can_edit_display_name ?? self;
  const canChangeStatus = editable && !self;
  const name = member.display_name || member.email;
  const activeLocations = locations.filter(isActiveLocation);
  const canChangeRole = editable && !self;
  const editing = view === "edit";
  const details = view === "details";
  const disabled = view === "status" && !member.is_disabled;
  const statusAction = member.is_disabled ? "Enable access" : "Disable access";
  const closeModal = useCallback(() => {
    // Carbon retains the opening Escape handler. Keep the mutation lock live.
    if (!inFlight.current) close.current();
  }, []);

  function show(next: View) {
    setError("");
    setView(next);
    if (next === "edit") setForm(editForm(member));
  }

  async function submit() {
    if (inFlight.current || (editing && (!editable || !formRef.current?.reportValidity())) || (!editing && !canChangeStatus)) return;
    inFlight.current = true;
    setBusy(true);
    setError("");
    try {
      const payload = editing ? userEditPayload(member, form) : { is_disabled: disabled };
      if (editing) {
        if (!canEditName) delete payload.display_name;
        if (!canChangeRole || payload.role === member.role) delete payload.role;
      }
      const updated: StaffMember = await updateUser(member.id, payload);
      if (!editing && updated.is_disabled !== disabled) {
        setError("This account still has an identity-level access restriction.");
        return;
      }
      onChanged(updated, editing ? "Team member updated." : disabled ? "Staff access disabled." : "Staff access enabled.");
      show("details");
    } catch (reason) {
      setError(adminError(reason, editing ? "Could not update the team member." : "Could not change staff access."));
    } finally {
      inFlight.current = false;
      setBusy(false);
    }
  }

  function submitForm(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void submit();
  }

  return (
    <div onKeyDownCapture={(event) => {
      if (event.key !== "Escape") return;
      event.preventDefault();
      event.stopPropagation();
      closeModal();
    }}>
      <Modal
        open size="sm" modalLabel={details ? undefined : name}
        modalHeading={details ? name : editing ? "Edit team member" : statusAction + "?"}
        passiveModal={details} danger={disabled}
        primaryButtonText={busy ? "Saving…" : editing ? "Save changes" : statusAction}
        primaryButtonDisabled={busy || (editing ? !editable : !canChangeStatus)}
        secondaryButtonText="Cancel"
        preventCloseOnClickOutside
        selectorPrimaryFocus={editing
          ? canEditName ? "#team-member-name" : canChangeRole ? "#team-member-role" : "#team-member-location"
          : details ? ".cds--modal-close" : ".cds--btn--secondary"}
        onRequestClose={closeModal}
        onSecondarySubmit={() => { if (!inFlight.current) show("details"); }}
        onRequestSubmit={() => void submit()}
      >
        {details ? (
          <Stack gap={5}>
            <dl className={styles.details}>
              <div><dt>Email</dt><dd>{member.email}</dd></div>
              <div><dt>Role</dt><dd>{roleName(member.role)}</dd></div>
              <div><dt>Organisation</dt><dd>{member.team.name}</dd></div>
              <div><dt>Default location</dt><dd>{locationName(member.default_location_id)}</dd></div>
              <div><dt>Status</dt><dd><Tag size="sm" type={member.is_disabled ? "gray" : "green"}>{member.is_disabled ? "Disabled" : "Active"}</Tag></dd></div>
            </dl>
            {editable && (
              <div className={styles.actions}>
                {!member.is_disabled && <Button size="sm" onClick={() => show("edit")}>Edit member</Button>}
                {canChangeStatus && (
                  <Button size="sm" kind={member.is_disabled ? "primary" : "danger--tertiary"} onClick={() => show("status")}>{statusAction}</Button>
                )}
              </div>
            )}
          </Stack>
        ) : (
          <Stack gap={5}>
            {error && <InlineNotification lowContrast kind="error" title="Change could not be saved" subtitle={error} hideCloseButton />}
            {editing ? (
              <form onSubmit={submitForm} ref={formRef}>
                <Stack gap={5}>
                  <TextInput
                    id="team-member-name" labelText="Display name" disabled={busy || !canEditName}
                    value={form.display_name} onChange={(event) => setForm({ ...form, display_name: event.target.value })}
                    maxLength={150}
                  />
                  <Select
                    id="team-member-role" labelText="Organisation role" disabled={busy || !canChangeRole}
                    value={form.role} onChange={(event) => setForm({ ...form, role: event.target.value })}
                  >
                    {!roles.some((role) => role.slug === form.role) && <SelectItem value={form.role} text={roleName(form.role)} />}
                    {roles.map((role) => <SelectItem key={role.id} value={role.slug} text={role.name} />)}
                  </Select>
                  <Select
                    id="team-member-location" labelText="Default location" disabled={busy}
                    value={form.default_location_id} onChange={(event) => setForm({ ...form, default_location_id: event.target.value })}
                  >
                    <SelectItem value="" text="No default" />
                    {member.default_location_id && !activeLocations.some((item) => item.id === member.default_location_id) && (
                      <SelectItem value={member.default_location_id} text={locationName(member.default_location_id)} />
                    )}
                    {activeLocations.map((item) => <SelectItem key={item.id} value={item.id} text={item.name} />)}
                  </Select>
                </Stack>
              </form>
            ) : (
              <>
                <p>{member.email} {disabled ? "will lose access to" : "will regain access to"} {member.team.name}.</p>
                {disabled && <p>Any existing Clerk membership will still occupy a staff place.</p>}
              </>
            )}
          </Stack>
        )}
      </Modal>
    </div>
  );
}
