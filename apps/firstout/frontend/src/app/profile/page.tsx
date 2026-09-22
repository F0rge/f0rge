"use client";

import {
  Button,
  InlineNotification,
  PasswordInput,
  Select,
  SelectItem,
  Stack,
  TextInput,
} from "@carbon/react";
import { FormEvent, useEffect, useState } from "react";

import { ApiError, isActiveLocation, listLocations, updateProfile, type Location } from "@/lib/api";
import { useAuth } from "@/lib/auth";

export default function ProfilePage() {
  const { user, refreshUser } = useAuth();
  const [displayName, setDisplayName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [defaultLocationId, setDefaultLocationId] = useState("");
  const [locations, setLocations] = useState<Location[]>([]);

  useEffect(() => {
    if (user) {
      setDisplayName(user.display_name ?? "");
      setEmail(user.email);
      setDefaultLocationId(user.default_location_id ?? "");
    }
  }, [user]);

  useEffect(() => {
    void listLocations()
      .then((data) => setLocations(data.filter(isActiveLocation)))
      .catch(() => setLocations([]));
  }, []);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  if (!user) {
    return null;
  }

  const sessionUser = user;

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setSuccess(false);
    setSubmitting(true);
    try {
      const payload: Parameters<typeof updateProfile>[0] = {
        display_name: displayName,
      };
      if (email !== sessionUser.email) {
        payload.email = email;
      }
      if (password) {
        payload.password = password;
      }
      const nextDefault = defaultLocationId || null;
      if (nextDefault !== (sessionUser.default_location_id ?? null)) {
        payload.default_location_id = nextDefault;
      }
      await updateProfile(payload);
      await refreshUser();
      setPassword("");
      setSuccess(true);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError(err instanceof Error ? err.message : "Failed to update profile.");
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Stack gap={6}>
      <div>
        <h1 className="cds--type-productive-heading-04">Profile</h1>
        <p className="cds--type-body-01">
          Update your display name and password. Role: {sessionUser.role} · Team:{" "}
          {sessionUser.team.name}
        </p>
      </div>

      {error ? (
        <InlineNotification
          kind="error"
          title="Update failed"
          subtitle={error}
          hideCloseButton
          lowContrast
        />
      ) : null}
      {success ? (
        <InlineNotification
          kind="success"
          title="Saved"
          subtitle="Your profile was updated."
          hideCloseButton
          lowContrast
        />
      ) : null}

      <form onSubmit={(event) => void onSubmit(event)} style={{ maxWidth: "24rem" }}>
        <Stack gap={5}>
          <TextInput
            id="profile-display-name"
            labelText="Display name"
            value={displayName}
            onChange={(event) => setDisplayName(event.target.value)}
            required
            disabled={submitting}
          />
          <TextInput
            id="profile-email"
            labelText="Email"
            type="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            disabled={submitting}
          />
          <PasswordInput
            id="profile-password"
            labelText="New password"
            helperText="Leave blank to keep your current password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            disabled={submitting}
          />
          <Select
            id="profile-default-location"
            labelText="Default location"
            helperText="Pre-selects on till when the location is a showroom"
            value={defaultLocationId}
            onChange={(event) => setDefaultLocationId(event.target.value)}
            disabled={submitting}
          >
            <SelectItem value="" text="No default" />
            {locations.map((loc) => (
              <SelectItem
                key={loc.id}
                value={loc.id}
                text={`${loc.name} (${loc.type})`}
              />
            ))}
          </Select>
          <Button type="submit" disabled={submitting}>
            {submitting ? "Saving…" : "Save changes"}
          </Button>
        </Stack>
      </form>
    </Stack>
  );
}
