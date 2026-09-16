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
  getBranding,
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
  const [waPhoneId, setWaPhoneId] = useState("");
  const [waBusinessId, setWaBusinessId] = useState("");
  const [waToken, setWaToken] = useState("");
  const [waAppSecret, setWaAppSecret] = useState("");
  const [waTemplate, setWaTemplate] = useState("");
  const [waLang, setWaLang] = useState("en");
  const [hasWaToken, setHasWaToken] = useState(false);
  const [hasWaAppSecret, setHasWaAppSecret] = useState(false);
  const [whatsappMode, setWhatsappMode] = useState<"off" | "click" | "cloud">("click");
  const [webhookUrl, setWebhookUrl] = useState("");

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
    setWaPhoneId(data.wa_phone_number_id ?? "");
    setWaBusinessId(data.wa_business_account_id ?? "");
    setWaTemplate(data.wa_invoice_template_name ?? "");
    setWaLang(data.wa_template_lang || "en");
    setHasWaToken(Boolean(data.has_wa_token));
    setHasWaAppSecret(Boolean(data.has_wa_app_secret));
    setWhatsappMode(data.whatsapp_mode ?? "click");
    setWaToken("");
    setWaAppSecret("");
  }, []);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const [data, branding] = await Promise.all([getCommsSettings(), getBranding()]);
        if (!cancelled) {
          apply(data);
          const origin = typeof window !== "undefined" ? window.location.origin : "";
          setWebhookUrl(`${origin}/api/v1/webhooks/whatsapp/${branding.slug}`);
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

  async function handleSaveWhatsApp() {
    setSaving(true);
    setError(null);
    setNotice(null);
    try {
      const payload: Parameters<typeof updateCommsSettings>[0] = {
        wa_phone_number_id: waPhoneId,
        wa_business_account_id: waBusinessId,
        wa_invoice_template_name: waTemplate,
        wa_template_lang: waLang,
      };
      if (waToken.length > 0) {
        payload.wa_access_token = waToken;
      }
      if (waAppSecret.length > 0) {
        payload.wa_app_secret = waAppSecret;
      }
      const saved = await updateCommsSettings(payload);
      apply(saved);
      setNotice("WhatsApp Cloud API saved. Secrets are not shown again.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save WhatsApp.");
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

      <div>
        <h3 className="cds--type-productive-heading-02">WhatsApp Cloud API</h3>
        <p className="cds--type-body-01 vellano-muted-text">
          Keep the WhatsApp Business app on this number. Paste the Cloud API token here; we do not
          replace the Business app. Unofficial WhatsApp libraries are not used.
        </p>
        <p className="cds--type-helper-text-01 vellano-muted-text">
          Mode: {whatsappMode === "cloud" ? "Cloud API" : "click-to-chat (wa.me)"}. Webhook:{" "}
          {webhookUrl || `${typeof window !== "undefined" ? window.location.origin : ""}/api/v1/webhooks/whatsapp/{slug}`}
        </p>
      </div>
      <TextInput
        id="wa-phone-id"
        labelText="Phone number ID"
        value={waPhoneId}
        disabled={!canMutate || saving}
        onChange={(event) => setWaPhoneId(event.target.value)}
      />
      <TextInput
        id="wa-business-id"
        labelText="Business account ID"
        value={waBusinessId}
        disabled={!canMutate || saving}
        onChange={(event) => setWaBusinessId(event.target.value)}
      />
      <TextInput
        id="wa-token"
        type="password"
        labelText="Access token"
        helperText={
          hasWaToken
            ? "Leave blank to keep the current token."
            : "Stored encrypted. Never returned on reload."
        }
        placeholder={hasWaToken ? "Leave blank to keep current" : undefined}
        value={waToken}
        disabled={!canMutate || saving}
        onChange={(event) => setWaToken(event.target.value)}
      />
      <TextInput
        id="wa-app-secret"
        type="password"
        labelText="App secret"
        helperText={
          hasWaAppSecret
            ? "Leave blank to keep the current secret. Used to verify webhook HMAC."
            : "Optional. Required for X-Hub-Signature-256 on the webhook."
        }
        placeholder={hasWaAppSecret ? "Leave blank to keep current" : undefined}
        value={waAppSecret}
        disabled={!canMutate || saving}
        onChange={(event) => setWaAppSecret(event.target.value)}
      />
      <TextInput
        id="wa-template"
        labelText="Utility template name"
        helperText="Create this template in WhatsApp Manager (for example invoice_notice)."
        value={waTemplate}
        disabled={!canMutate || saving}
        onChange={(event) => setWaTemplate(event.target.value)}
      />
      <TextInput
        id="wa-lang"
        labelText="Template language"
        value={waLang}
        disabled={!canMutate || saving}
        onChange={(event) => setWaLang(event.target.value)}
      />
      {canMutate ? (
        <Button kind="primary" disabled={saving} onClick={() => void handleSaveWhatsApp()}>
          {saving ? "Saving…" : "Save WhatsApp"}
        </Button>
      ) : null}
    </Stack>
  );
}
