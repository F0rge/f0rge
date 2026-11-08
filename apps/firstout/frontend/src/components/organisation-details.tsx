"use client";

import { Button, FileUploaderButton, InlineNotification, Stack, TextArea, TextInput } from "@carbon/react";
import { useState, type FormEvent } from "react";
import { settingsLogoUrl, updateSettings, uploadCompanyLogo, type AppSettings } from "@/lib/api";
import { StaffImage } from "./staff-image";

export function OrganisationDetails({ initial }: { initial: AppSettings }) {
  const [legalName, setLegalName] = useState(initial.legal_name);
  const [tradingName, setTradingName] = useState(initial.trading_name ?? "");
  const [address, setAddress] = useState(initial.address);
  const [vatNumber, setVatNumber] = useState(initial.vat_number);
  const [hasLogo, setHasLogo] = useState(initial.has_logo);
  const [logoVersion, setLogoVersion] = useState(0);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true); setError(null); setNotice(null);
    try {
      await updateSettings({ legal_name: legalName.trim(), trading_name: tradingName.trim() || null, address: address.trim(), vat_number: vatNumber.trim() });
      setNotice("Business details saved.");
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Unable to save business details."); }
    finally { setSaving(false); }
  }

  async function upload(file: File) {
    setSaving(true); setError(null); setNotice(null);
    try {
      const saved = await uploadCompanyLogo(file);
      setHasLogo(saved.has_logo); setLogoVersion((value) => value + 1);
      setNotice("Business logo saved.");
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Unable to upload the logo."); }
    finally { setSaving(false); }
  }

  return <Stack gap={5}>
    <h2 className="cds--type-productive-heading-03">Business details and branding</h2>
    {error ? <InlineNotification kind="error" title="Changes weren’t saved" subtitle={error} hideCloseButton lowContrast /> : null}
    {notice ? <InlineNotification kind="success" title={notice} hideCloseButton lowContrast /> : null}
    <form onSubmit={(event) => void save(event)}><Stack gap={5}>
      <div className="firstout-organisation-form-grid">
        <TextInput id="business-legal-name" labelText="Legal business name" value={legalName} required disabled={saving} onChange={(event) => setLegalName(event.target.value)} />
        <TextInput id="business-trading-name" labelText="Trading name (optional)" value={tradingName} disabled={saving} onChange={(event) => setTradingName(event.target.value)} />
      </div>
      <TextArea id="business-address" labelText="Business address" value={address} rows={3} disabled={saving} onChange={(event) => setAddress(event.target.value)} />
      <TextInput id="business-vat-number" labelText="VAT number (optional)" value={vatNumber} disabled={saving} onChange={(event) => setVatNumber(event.target.value)} />
      <Button type="submit" disabled={saving || !legalName.trim()}>{saving ? "Saving…" : "Save business details"}</Button>
    </Stack></form>
    {hasLogo ? <StaffImage src={`${settingsLogoUrl()}?v=${logoVersion}`} alt="Business logo" className="firstout-organisation-logo" /> : <p>No business logo uploaded.</p>}
    <FileUploaderButton id="business-logo" labelText={hasLogo ? "Replace business logo" : "Upload business logo"} accept={["image/png", "image/jpeg", "image/webp"]} multiple={false} disabled={saving}
      onChange={(event) => { const file = event.target.files?.[0]; if (file) void upload(file); event.target.value = ""; }} />
  </Stack>;
}
