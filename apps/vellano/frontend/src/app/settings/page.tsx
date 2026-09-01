"use client";

import {
  Button,
  InlineNotification,
  Loading,
  NumberInput,
  Select,
  SelectItem,
  Stack,
  TextInput,
  Tile,
  Toggle,
} from "@carbon/react";
import { ChevronDown, ChevronUp, Close } from "@carbon/icons-react";
import { useEffect, useState } from "react";

import {
  ApiError,
  canMutateSettings,
  getSettings,
  isActiveLocation,
  listLocations,
  updateSettings,
  type AppSettings,
  type Location,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";

export default function SettingsPage() {
  const { user } = useAuth();
  const canMutate = canMutateSettings(user);
  const [settings, setSettings] = useState<AppSettings | null>(null);
  const [vatPercent, setVatPercent] = useState("15");
  const [currency, setCurrency] = useState("ZAR");
  const [preferWarehouse, setPreferWarehouse] = useState(true);
  const [pickPriority, setPickPriority] = useState<string[]>([]);
  const [locations, setLocations] = useState<Location[]>([]);
  const [addLocationId, setAddLocationId] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    Promise.all([getSettings(), listLocations()])
      .then(([data, locationData]) => {
        if (!cancelled) {
          setSettings(data);
          setVatPercent(data.vat_percent);
          setCurrency(data.home_currency);
          setPreferWarehouse(data.always_prefer_warehouse);
          setPickPriority(data.pick_priority);
          setLocations(locationData.filter(isActiveLocation));
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
        always_prefer_warehouse: preferWarehouse,
        pick_priority: pickPriority,
      });
      setSettings(updated);
      setVatPercent(updated.vat_percent);
      setCurrency(updated.home_currency);
      setPreferWarehouse(updated.always_prefer_warehouse);
      setPickPriority(updated.pick_priority);
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
            <Toggle
              id="always-prefer-warehouse"
              labelText="Always prefer warehouse"
              labelA="Off"
              labelB="On"
              toggled={preferWarehouse}
              onToggle={(checked) => setPreferWarehouse(checked)}
              disabled={!canMutate || saving}
            />
            <Stack gap={3}>
              <p className="cds--label">Pick priority</p>
              <p className="vellano-muted-text">
                Ordered location list for kit picks. Empty derives order by location type.
              </p>
              {pickPriority.length === 0 ? (
                <p className="cds--type-body-01">No priority set — derive by type.</p>
              ) : (
                pickPriority.map((locationId, index) => {
                  const location = locations.find((entry) => entry.id === locationId);
                  return (
                    <div key={locationId} className="vellano-pick-priority-row">
                      <span>
                        {index + 1}. {location?.name ?? locationId}
                      </span>
                      <div className="vellano-catalogue-actions">
                        <Button
                          kind="ghost"
                          size="sm"
                          hasIconOnly
                          renderIcon={ChevronUp}
                          iconDescription="Move up"
                          disabled={!canMutate || saving || index === 0}
                          onClick={() =>
                            setPickPriority((current) => {
                              const next = [...current];
                              const swap = next[index - 1];
                              next[index - 1] = next[index];
                              next[index] = swap;
                              return next;
                            })
                          }
                        />
                        <Button
                          kind="ghost"
                          size="sm"
                          hasIconOnly
                          renderIcon={ChevronDown}
                          iconDescription="Move down"
                          disabled={!canMutate || saving || index === pickPriority.length - 1}
                          onClick={() =>
                            setPickPriority((current) => {
                              const next = [...current];
                              const swap = next[index + 1];
                              next[index + 1] = next[index];
                              next[index] = swap;
                              return next;
                            })
                          }
                        />
                        <Button
                          kind="ghost"
                          size="sm"
                          hasIconOnly
                          renderIcon={Close}
                          iconDescription="Remove"
                          disabled={!canMutate || saving}
                          onClick={() =>
                            setPickPriority((current) => current.filter((id) => id !== locationId))
                          }
                        />
                      </div>
                    </div>
                  );
                })
              )}
              <Select
                id="add-pick-priority"
                labelText="Add location"
                value={addLocationId}
                disabled={!canMutate || saving}
                onChange={(event) => {
                  const nextId = event.target.value;
                  if (!nextId) {
                    return;
                  }
                  setPickPriority((current) =>
                    current.includes(nextId) ? current : [...current, nextId],
                  );
                  setAddLocationId("");
                }}
              >
                <SelectItem value="" text="Select location" />
                {locations
                  .filter((location) => !pickPriority.includes(location.id))
                  .map((location) => (
                    <SelectItem key={location.id} value={location.id} text={location.name} />
                  ))}
              </Select>
            </Stack>
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
