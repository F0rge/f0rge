"use client";

import { ChevronDown, ChevronRight } from "@carbon/icons-react";
import { Button, InlineNotification, Select, SelectItem, Stack, Table, TableBody, TableCell, TableContainer, TableHead, TableHeader, TableRow, TextInput } from "@carbon/react";
import { useUser } from "@clerk/nextjs";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { AdminPageHeader } from "@/components/administration";
import { AdminSaveActions, confirmDiscardChanges } from "@/components/admin-save-actions";
import { ClerkAccountButton } from "@/components/clerk-account-button";
import { ADMIN_DESTINATIONS } from "@/lib/admin-navigation";
import { isActiveLocation, listLocations, updateProfile, type AuthUser, type Location } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { adminError } from "@/lib/staff-administration";
import styles from "./profile.module.css";

function preferences(user: AuthUser) {
  return { displayName: user.display_name ?? "", defaultLocationId: user.default_location_id ?? "" };
}

function ProfileScreen({ user }: { user: AuthUser }) {
  const { refreshUser } = useAuth();
  const { user: clerkUser } = useUser();
  const [saved, setSaved] = useState(() => preferences(user));
  const [draft, setDraft] = useState(saved);
  const [locations, setLocations] = useState<Location[] | null>(null);
  const [locationError, setLocationError] = useState("");
  const [locationAttempt, setLocationAttempt] = useState(0);
  const [section, setSection] = useState<"preferences" | "security" | null>(null);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);
  const [saving, setSaving] = useState(false);
  const displayNameInput = useRef<HTMLInputElement>(null);
  const busy = useRef(false);
  const email = clerkUser?.primaryEmailAddress?.emailAddress ?? user.email;
  const dirty = draft.displayName !== saved.displayName || draft.defaultLocationId !== saved.defaultLocationId;
  const activeLocations = locations?.filter(isActiveLocation) ?? [];
  const savedLocation = locations?.find(({ id }) => id === saved.defaultLocationId);
  const currentLocationLabel = saved.defaultLocationId
    ? savedLocation ? savedLocation.name : locations || locationError ? "Default location unavailable" : "Loading default location…"
    : "No default location";
  const { label, description } = ADMIN_DESTINATIONS.profile;

  useEffect(() => {
    let active = true;
    listLocations().then(
      (data) => { if (active) setLocations(data); },
      (reason: unknown) => { if (active) setLocationError(adminError(reason, "Could not load locations.")); },
    );
    return () => { active = false; };
  }, [locationAttempt]);

  function selectSection(next: "preferences" | "security") {
    if (busy.current || !confirmDiscardChanges(dirty)) return;
    setDraft(saved);
    setError("");
    const open = section === next ? null : next;
    setSection(open);
    if (open === "preferences") requestAnimationFrame(() => displayNameInput.current?.focus());
  }

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy.current || !dirty || !draft.displayName.trim()) return;
    busy.current = true;
    setSaving(true);
    setError("");
    setSuccess(false);
    try {
      const payload: Parameters<typeof updateProfile>[0] = { display_name: draft.displayName.trim() };
      if (draft.defaultLocationId !== saved.defaultLocationId) {
        payload.default_location_id = draft.defaultLocationId || null;
      }
      const updated = preferences(await updateProfile(payload));
      setSaved(updated);
      setDraft(updated);
      setSuccess(true);
      await refreshUser();
    } catch (reason) {
      setError(adminError(reason, "Could not update your profile."));
    } finally {
      busy.current = false;
      setSaving(false);
    }
  }

  return (
    <Stack gap={6}>
      <AdminPageHeader title={label} description={description} />
      {success ? <InlineNotification kind="success" title="Changes saved" subtitle="Your workspace preferences were updated." lowContrast onCloseButtonClick={() => setSuccess(false)} /> : null}
      <TableContainer title="Account settings">
        <Table size="lg" aria-label="Account settings" className={styles.table}>
          <TableHead>
            <TableRow><TableHeader scope="col">Account setting</TableHeader><TableHeader scope="col">Current value</TableHeader></TableRow>
          </TableHead>
          <TableBody>
            <TableRow>
              <TableCell>
                <button className={styles.rowButton} aria-expanded={section === "preferences"} onClick={() => selectSection("preferences")} type="button">
                  {section === "preferences" ? <ChevronDown size={16} aria-hidden="true" /> : <ChevronRight size={16} aria-hidden="true" />}
                  Workspace preferences
                </button>
              </TableCell>
              <TableCell>{saved.displayName || email} · {currentLocationLabel}</TableCell>
            </TableRow>
            {section === "preferences" ? (
              <TableRow>
                <TableCell colSpan={2} className={styles.panel}>
                  <form onSubmit={(event) => void save(event)}>
                    <Stack gap={5}>
                      <h2 className="cds--type-heading-03">Workspace preferences</h2>
                      {error ? <InlineNotification kind="error" title="Changes could not be saved" subtitle={error} lowContrast hideCloseButton /> : null}
                      {locationError ? (
                        <div className={styles.retry}>
                          <InlineNotification kind="error" title="Locations unavailable" subtitle={locationError} lowContrast hideCloseButton />
                          <Button size="sm" kind="tertiary" onClick={() => { setLocationError(""); setLocationAttempt((value) => value + 1); }}>Try again</Button>
                        </div>
                      ) : null}
                      <div className={styles.fields}>
                        <TextInput ref={displayNameInput} id="profile-display-name" labelText="Display name" value={draft.displayName} required disabled={saving}
                          onChange={(event) => setDraft((value) => ({ ...value, displayName: event.target.value }))} />
                        <Select id="profile-default-location" labelText="Default location" value={draft.defaultLocationId} disabled={saving || !locations}
                          helperText={locations ? "Preselected at the till when your default is a showroom." : locationError ? "Your current preference is preserved." : "Loading locations…"}
                          onChange={(event) => setDraft((value) => ({ ...value, defaultLocationId: event.target.value }))}>
                          <SelectItem value="" text="No default" />
                          {saved.defaultLocationId && !activeLocations.some(({ id }) => id === saved.defaultLocationId) ? (
                            <SelectItem value={saved.defaultLocationId} text={currentLocationLabel} disabled />
                          ) : null}
                          {activeLocations.map(({ id, name, type }) => <SelectItem key={id} value={id} text={`${name} (${type})`} />)}
                        </Select>
                      </div>
                      <AdminSaveActions canMutate dirty={dirty} saving={saving} saveDisabled={!draft.displayName.trim()} onDiscard={() => { setDraft(saved); setError(""); setSuccess(false); }} />
                    </Stack>
                  </form>
                </TableCell>
              </TableRow>
            ) : null}
            <TableRow>
              <TableCell>
                <button className={styles.rowButton} aria-expanded={section === "security"} onClick={() => selectSection("security")} type="button">
                  {section === "security" ? <ChevronDown size={16} aria-hidden="true" /> : <ChevronRight size={16} aria-hidden="true" />}
                  Sign-in and security
                </button>
              </TableCell>
              <TableCell>{email}</TableCell>
            </TableRow>
            {section === "security" ? (
              <TableRow>
                <TableCell colSpan={2} className={styles.panel}>
                  <Stack gap={4}>
                    <h2 className="cds--type-heading-03">Sign-in and security</h2>
                    <p>Manage your sign-in methods, devices and account security in Clerk.</p>
                    <div><ClerkAccountButton /></div>
                  </Stack>
                </TableCell>
              </TableRow>
            ) : null}
          </TableBody>
        </Table>
      </TableContainer>
    </Stack>
  );
}

export default function ProfilePage() {
  const { user } = useAuth();
  return user ? <ProfileScreen key={`${user.team.id}:${user.id}`} user={user} /> : null;
}
