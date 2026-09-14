"use client";

import {
  Button,
  InlineNotification,
  NumberInput,
  Select,
  SelectItem,
  Stack,
  TextInput,
} from "@carbon/react";
import { useCallback, useEffect, useState } from "react";

import {
  canMutateSettings,
  getCommsSettings,
  testCommsEmail,
  updateCommsSettings,
  type CommsSettings,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";

function asPort(value: number | string | undefined): number | "" {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }
  return "";
}

export function CommunicationsSettings() {
  const { user } = useAuth();
  const canMutate = canMutateSettings(user);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [host, setHost] = useState("");
  const [port, setPort] = useState<number | "">(587);
  const [security, setSecurity] = useState("starttls");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [fromAddress, setFromAddress] = useState("");
  const [fromName, setFromName] = useState("");
  const [replyTo, setReplyTo] = useState("");
  const [hasPassword, setHasPassword] = useState(false);
  const [testTo, setTestTo] = useState("");

  const apply = useCallback((data: CommsSettings) => {
    setHost(data.smtp_host ?? "");
    setPort(data.smtp_port ?? 587);
    setSecurity(data.smtp_security || "starttls");
    setUsername(data.smtp_username ?? "");
    setFromAddress(data.smtp_from_address ?? "");
    setFromName(data.smtp_from_name ?? "");
    setReplyTo(data.smtp_reply_to ?? "");
    setHasPassword(data.has_smtp_password);
    setPassword("");
  }, []);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const data = await getCommsSettings();
        if (!cancelled) {
          apply(data);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load communications.");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [apply]);

  async function handleSave() {
    setSaving(true);
    setError(null);
    setNotice(null);
    try {
      const payload: Parameters<typeof updateCommsSettings>[0] = {
        smtp_host: host,
        smtp_port: typeof port === "number" ? port : null,
        smtp_security: security,
        smtp_username: username,
        smtp_from_address: fromAddress,
        smtp_from_name: fromName,
        smtp_reply_to: replyTo,
      };
      if (password.length > 0) {
        payload.smtp_password = password;
      }
      const saved = await updateCommsSettings(payload);
      apply(saved);
      setNotice("Mailbox saved. The password is not shown again.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save mailbox.");
    } finally {
      setSaving(false);
    }
  }

  async function handleTest() {
    setTesting(true);
    setError(null);
    setNotice(null);
    try {
      await testCommsEmail(testTo);
      setNotice(`Test email accepted for ${testTo}.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Test send failed.");
    } finally {
      setTesting(false);
    }
  }

  if (loading) {
    return <p className="cds--type-body-01">Loading communications…</p>;
  }

  return (
    <Stack gap={5}>
      <div>
        <h2 className="cds--type-productive-heading-03">Communications</h2>
        <p className="cds--type-body-01 vellano-muted-text">
          Use the mailbox your ISP or Microsoft 365 gave you (SMTP). This is not Gmail API.
        </p>
      </div>
      {notice ? (
        <InlineNotification
          kind="success"
          title="Saved"
          subtitle={notice}
          onCloseButtonClick={() => setNotice(null)}
          lowContrast
        />
      ) : null}
      {error ? (
        <InlineNotification
          kind="error"
          title="Error"
          subtitle={error}
          onCloseButtonClick={() => setError(null)}
          lowContrast
        />
      ) : null}
      {!canMutate ? (
        <InlineNotification
          kind="info"
          title="Read only"
          subtitle="You can view the mailbox. Connecting accounts needs settings permission."
          hideCloseButton
        />
      ) : null}
      <TextInput
        id="smtp-host"
        labelText="SMTP host"
        value={host}
        disabled={!canMutate || saving}
        onChange={(event) => setHost(event.target.value)}
      />
      <NumberInput
        id="smtp-port"
        label="Port"
        min={1}
        max={65535}
        step={1}
        value={port}
        disabled={!canMutate || saving}
        onChange={(_, { value }) => setPort(asPort(value))}
      />
      <Select
        id="smtp-security"
        labelText="Security"
        value={security}
        disabled={!canMutate || saving}
        onChange={(event) => setSecurity(event.target.value)}
      >
        <SelectItem value="starttls" text="STARTTLS (587)" />
        <SelectItem value="ssl" text="SSL (465)" />
        <SelectItem value="plain" text="Plain (only if your host requires it)" />
      </Select>
      <TextInput
        id="smtp-username"
        labelText="Username"
        value={username}
        disabled={!canMutate || saving}
        onChange={(event) => setUsername(event.target.value)}
      />
      <TextInput
        id="smtp-password"
        type="password"
        labelText="Password"
        helperText={
          hasPassword
            ? "Leave blank to keep the current password."
            : "Stored encrypted. Never returned on reload."
        }
        placeholder={hasPassword ? "Leave blank to keep current" : undefined}
        value={password}
        disabled={!canMutate || saving}
        onChange={(event) => setPassword(event.target.value)}
      />
      <TextInput
        id="smtp-from"
        labelText="From address"
        value={fromAddress}
        disabled={!canMutate || saving}
        onChange={(event) => setFromAddress(event.target.value)}
      />
      <TextInput
        id="smtp-from-name"
        labelText="From name"
        value={fromName}
        disabled={!canMutate || saving}
        onChange={(event) => setFromName(event.target.value)}
      />
      <TextInput
        id="smtp-reply-to"
        labelText="Reply-To"
        value={replyTo}
        disabled={!canMutate || saving}
        onChange={(event) => setReplyTo(event.target.value)}
      />
      {canMutate ? (
        <Button kind="primary" disabled={saving} onClick={() => void handleSave()}>
          {saving ? "Saving…" : "Save mailbox"}
        </Button>
      ) : null}
      <TextInput
        id="smtp-test-to"
        labelText="Test send to"
        value={testTo}
        disabled={!canMutate || testing}
        onChange={(event) => setTestTo(event.target.value)}
      />
      {canMutate ? (
        <Button
          kind="secondary"
          disabled={testing || !testTo.trim()}
          onClick={() => void handleTest()}
        >
          {testing ? "Sending…" : "Send test email"}
        </Button>
      ) : null}
    </Stack>
  );
}
