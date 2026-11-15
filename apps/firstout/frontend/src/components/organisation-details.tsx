"use client";

import {
  Button,
  FileUploaderButton,
  InlineNotification,
  Stack,
  Tag,
  TextArea,
  TextInput,
  Tile,
} from "@carbon/react";
import { Building } from "@carbon/icons-react";
import { useState, type FormEvent, type ReactNode } from "react";
import {
  settingsLogoUrl,
  updateSettings,
  uploadCompanyLogo,
  type AppSettings,
} from "@/lib/api";
import { StaffImage } from "./staff-image";
import styles from "@/app/organisation/organisation.module.css";

function businessValues(settings: AppSettings) {
  return {
    legalName: settings.legal_name,
    tradingName: settings.trading_name ?? "",
    address: settings.address,
    vatNumber: settings.vat_number,
  };
}

export function OrganisationDetails({
  initial,
  children,
}: {
  initial: AppSettings;
  children?: ReactNode;
}) {
  const [saved, setSaved] = useState(() => businessValues(initial));
  const [draft, setDraft] = useState(() => businessValues(initial));
  const [hasLogo, setHasLogo] = useState(initial.has_logo);
  const [logoVersion, setLogoVersion] = useState(0);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const dirty = JSON.stringify(draft) !== JSON.stringify(saved);
  const patch = (key: keyof typeof draft, value: string) =>
    setDraft((current) => ({ ...current, [key]: value }));

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (saving || !dirty || !draft.legalName.trim()) return;
    setSaving(true);
    setError(null);
    setNotice(null);
    try {
      const updated = await updateSettings({
        legal_name: draft.legalName.trim(),
        trading_name: draft.tradingName.trim() || null,
        address: draft.address.trim(),
        vat_number: draft.vatNumber.trim(),
      });
      const values = businessValues(updated);
      setSaved(values);
      setDraft(values);
      setNotice("Business details saved.");
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "Unable to save business details.",
      );
    } finally {
      setSaving(false);
    }
  }

  async function upload(file: File) {
    if (saving) return;
    setSaving(true);
    setError(null);
    setNotice(null);
    try {
      const updated = await uploadCompanyLogo(file);
      setHasLogo(updated.has_logo);
      setLogoVersion((value) => value + 1);
      setNotice("Business logo saved.");
    } catch (reason) {
      setError(
        reason instanceof Error ? reason.message : "Unable to upload the logo.",
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <Stack gap={5}>
      {error ? (
        <InlineNotification
          kind="error"
          title="Changes weren’t saved"
          subtitle={error}
          hideCloseButton
          lowContrast
        />
      ) : null}
      {notice ? (
        <InlineNotification
          kind="success"
          title={notice}
          hideCloseButton
          lowContrast
        />
      ) : null}
      <div className={styles.profileGrid}>
        <Tile>
          <Stack gap={5}>
            <div className={styles.headingRow}>
              <h2 className="cds--type-heading-03">Business details</h2>
              <Tag type="gray">Identity</Tag>
            </div>
            <form onSubmit={(event) => void save(event)}>
              <Stack gap={5}>
                <div className={styles.businessGrid}>
                  <TextInput
                    id="business-legal-name"
                    labelText="Legal business name"
                    value={draft.legalName}
                    required
                    disabled={saving}
                    onChange={(event) => patch("legalName", event.target.value)}
                  />
                  <TextInput
                    id="business-trading-name"
                    labelText="Trading name (optional)"
                    value={draft.tradingName}
                    disabled={saving}
                    onChange={(event) =>
                      patch("tradingName", event.target.value)
                    }
                  />
                </div>
                <TextArea
                  id="business-address"
                  labelText="Business address"
                  value={draft.address}
                  rows={3}
                  disabled={saving}
                  onChange={(event) => patch("address", event.target.value)}
                />
                <TextInput
                  id="business-vat-number"
                  labelText="VAT number (optional)"
                  value={draft.vatNumber}
                  disabled={saving}
                  onChange={(event) => patch("vatNumber", event.target.value)}
                />
                <div className={styles.actions}>
                  <Button
                    type="submit"
                    disabled={saving || !dirty || !draft.legalName.trim()}
                  >
                    {saving ? "Saving…" : "Save business details"}
                  </Button>
                  <Button
                    kind="ghost"
                    disabled={saving || !dirty}
                    onClick={() => {
                      setDraft(saved);
                      setError(null);
                      setNotice(null);
                    }}
                  >
                    Discard changes
                  </Button>
                  {dirty ? <Tag type="warm-gray">Unsaved changes</Tag> : null}
                </div>
              </Stack>
            </form>
          </Stack>
        </Tile>
        <Stack gap={6}>
          {children}
          <Tile>
            <Stack gap={5}>
              <div className={styles.headingRow}>
                <h2 className="cds--type-heading-03">Branding</h2>
                <Tag type="gray">Documents</Tag>
              </div>
              <div className={`${styles.branding} firstout-tone-info`}>
                {hasLogo ? (
                  <StaffImage
                    src={`${settingsLogoUrl()}?v=${logoVersion}`}
                    alt="Business logo"
                    className={styles.logo}
                  />
                ) : (
                  <Building size={48} aria-hidden="true" />
                )}
                <div>
                  <p className="cds--type-heading-compact-01">
                    {saved.tradingName || saved.legalName}
                  </p>
                  <p className="cds--type-helper-text-01">
                    {hasLogo
                      ? "Logo on invoices and documents"
                      : "No business logo uploaded"}
                  </p>
                </div>
              </div>
              <FileUploaderButton
                id="business-logo"
                labelText={
                  hasLogo ? "Replace business logo" : "Upload business logo"
                }
                accept={["image/png", "image/jpeg", "image/webp"]}
                multiple={false}
                disabled={saving}
                onChange={(event) => {
                  const file = event.target.files?.[0];
                  if (file) void upload(file);
                  event.target.value = "";
                }}
              />
              <p className="cds--type-helper-text-01">
                PNG, JPEG or WebP. Uploading replaces the existing logo.
              </p>
            </Stack>
          </Tile>
        </Stack>
      </div>
    </Stack>
  );
}
