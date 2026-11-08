"use client";

import { Button, Stack, TextArea, TextInput } from "@carbon/react";
import { useState, type FormEvent } from "react";
import { suggestedOrganisationSlug, tenantSubdomainsEnabled, validOrganisationSlug, type CreateOrganisation } from "@/lib/organisations";

type Props = {
  submitting: boolean;
  onSubmit: (body: CreateOrganisation) => Promise<void>;
};

export function OrganisationForm({ submitting, onSubmit }: Props) {
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [slugEdited, setSlugEdited] = useState(false);
  const [legalName, setLegalName] = useState("");
  const [address, setAddress] = useState("");
  const [vatNumber, setVatNumber] = useState("");
  const [locationName, setLocationName] = useState("Main location");
  const slugValid = validOrganisationSlug(slug);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!slugValid || !name.trim() || !locationName.trim()) return;
    await onSubmit({
      name: name.trim(), slug, location_name: locationName.trim(),
      legal_name: legalName.trim() || undefined,
      address: address.trim() || undefined,
      vat_number: vatNumber.trim() || undefined,
    });
  }

  return <form onSubmit={(event) => void submit(event)}>
    <Stack gap={5}>
      <TextInput id="organisation-name" labelText="Business name" value={name} maxLength={255} required disabled={submitting}
        onChange={(event) => {
          const next = event.target.value;
          setName(next);
          if (!slugEdited) setSlug(suggestedOrganisationSlug(next));
        }} />
      <TextInput id="organisation-slug" labelText={tenantSubdomainsEnabled ? "Business web address" : "Business short name"} value={slug} maxLength={63} required disabled={submitting}
        helperText={tenantSubdomainsEnabled ? `${slug || "your-business"}.app.firstout.co.za` : "A unique short name for your organisation. Use lowercase letters, numbers and hyphens."}
        invalid={Boolean(slug) && !slugValid}
        invalidText="Use lowercase letters, numbers and hyphens between words. Choose a non-reserved name."
        onChange={(event) => { setSlugEdited(true); setSlug(event.target.value); }} />
      <div className="firstout-organisation-form-grid">
        <TextInput id="organisation-legal-name" labelText="Legal business name (optional)" value={legalName} maxLength={255} disabled={submitting} onChange={(event) => setLegalName(event.target.value)} />
        <TextInput id="organisation-vat" labelText="VAT number (optional)" value={vatNumber} maxLength={64} disabled={submitting} onChange={(event) => setVatNumber(event.target.value)} />
      </div>
      <TextArea id="organisation-address" labelText="Business address (optional)" value={address} maxLength={2000} rows={3} disabled={submitting} onChange={(event) => setAddress(event.target.value)} />
      <TextInput id="organisation-location" labelText="First location" helperText="Your first warehouse or shop. You can add more locations later." value={locationName} maxLength={255} required disabled={submitting} onChange={(event) => setLocationName(event.target.value)} />
      <p className="cds--type-helper-text-01">Free for up to five staff members, including you. You can add your logo, label preferences and staff after creating the organisation.</p>
      <Button type="submit" disabled={submitting || !slugValid || !name.trim() || !locationName.trim()}>{submitting ? "Creating organisation…" : "Create organisation"}</Button>
    </Stack>
  </form>;
}
