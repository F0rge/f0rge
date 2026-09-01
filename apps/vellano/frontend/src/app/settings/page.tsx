"use client";

import {
  Button,
  InlineNotification,
  Loading,
  NumberInput,
  Stack,
  TextInput,
  Tile,
} from "@carbon/react";
import { useEffect, useState } from "react";

import {
  ApiError,
  canMutateSettings,
  getSettings,
  updateSettings,
  type AppSettings,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";

export default function SettingsPage() {
  const { user } = useAuth();
  const canMutate = canMutateSettings(user);
  const [settings, setSettings] = useState<AppSettings | null>(null);
  const [vatPercent, setVatPercent] = useState("15");
  const [currency, setCurrency] = useState("ZAR");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getSettings()
      .then((data) => {
        if (!cancelled) {
          setSettings(data);
          setVatPercent(data.vat_percent);
          setCurrency(data.home_currency);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof ApiError ? err.message : "Failed to load settings");
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function handleSave() {
    setSaving(true);
    setError(null);
    setNotice(null);
    try {
      const vatRate = (Number(vatPercent) / 100).toFixed(4);
      const updated = await updateSettings({
        vat_rate: vatRate,
        home_currency: currency.toUpperCase(),
      });
      setSettings(updated);
      setVatPercent(updated.vat_percent);
      setCurrency(updated.home_currency);
      setNotice(updated.warning ?? "Settings saved.");
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.message : "Failed to save settings");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Stack gap={6}>
      <div>
        <h1 className="cds--type-productive-heading-04">Settings</h1>
        <p className="cds--type-body-01">
          Vellano V1 defaults: VAT 15% and home currency ZAR. Changes are not filed with SARS.
        </p>
      </div>

      {loading ? <Loading withOverlay={false} description="Loading settings…" /> : null}
      {error ? (
        <InlineNotification kind="error" title="Settings" subtitle={error} hideCloseButton />
      ) : null}
      {notice ? (
        <InlineNotification kind="info" title="Settings" subtitle={notice} hideCloseButton />
      ) : null}
      {settings?.warning && !notice ? (
        <InlineNotification
          kind="warning"
          title="Non-default settings"
          subtitle={settings.warning}
          hideCloseButton
        />
      ) : null}

      {settings ? (
        <Tile>
          <Stack gap={5}>
            <NumberInput
              id="vat-percent"
              label="VAT rate (%)"
              helperText="Locked default is 15%. Owner may adjust for what-if only."
              value={vatPercent}
              min={0}
              max={100}
              step={0.01}
              disabled={!canMutate || saving}
              onChange={(_, { value }) => {
                if (typeof value === "number" || typeof value === "string") {
                  setVatPercent(String(value));
                }
              }}
            />
            <TextInput
              id="home-currency"
              labelText="Home currency"
              helperText="Locked default is ZAR."
              value={currency}
              maxLength={3}
              disabled={!canMutate || saving}
              onChange={(event) => setCurrency(event.target.value.toUpperCase())}
            />
            {canMutate ? (
              <Button kind="primary" disabled={saving} onClick={() => void handleSave()}>
                {saving ? "Saving…" : "Save settings"}
              </Button>
            ) : (
              <InlineNotification
                kind="info"
                title="Read only"
                subtitle="Only the owner can change VAT or home currency."
                hideCloseButton
              />
            )}
          </Stack>
        </Tile>
      ) : null}
    </Stack>
  );
}
