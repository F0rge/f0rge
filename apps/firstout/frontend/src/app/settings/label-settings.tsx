"use client";
import {
  Checkbox,
  InlineNotification,
  NumberInput,
  Stack,
} from "@carbon/react";
import { useLayoutEffect, useState } from "react";
import { updateSettings, type AppSettings } from "@/lib/api";
import { AdminSaveActions } from "@/components/admin-save-actions";
import { changedSettingsFields, useSettingsDrafts } from "@/components/settings-drafts";
import styles from "./settings.module.css";
import type { LabelSettings as LabelValues } from "@/lib/label-settings";

function labelValues(settings: AppSettings): LabelValues {
  return {
    label_width_mm: settings.label_width_mm,
    label_height_mm: settings.label_height_mm,
    label_show_name: settings.label_show_name,
    label_show_reference: settings.label_show_reference,
    label_show_barcode: settings.label_show_barcode,
    label_show_logo: settings.label_show_logo,
  };
}

export function LabelSettings({
  settings,
  canMutate,
}: {
  settings: AppSettings;
  canMutate: boolean;
}) {
  const [saved, setSaved] = useState<LabelValues>(() => labelValues(settings));
  const drafts = useSettingsDrafts();
  const [values, setValues] = useState(() => labelValues({ ...settings, ...(canMutate ? drafts.get("labels")?.fields : {}) }));
  const changed = changedSettingsFields(saved, values);
  const dirty = Object.keys(changed).length > 0;
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState(false);
  useLayoutEffect(() => {
    drafts.set("labels", dirty && canMutate ? { fields: changed } : undefined);
  });
  async function save() {
    const submittedDraft = drafts.get("labels");
    setSaving(true);
    setMessage(null);
    try {
      const updated = labelValues(await updateSettings(changed));
      if (drafts.get("labels") === submittedDraft) drafts.set("labels");
      setSaved(updated);
      setValues(updated);
      setError(false);
      setMessage("Label settings saved for your organisation.");
    } catch (err) {
      setError(true);
      setMessage(
        err instanceof Error ? err.message : "Unable to save label settings.",
      );
    } finally {
      setSaving(false);
    }
  }
  return (
    <Stack gap={5}>
      <p>SKU and bin labels use these settings and your company logo.</p>
      <div className={styles.formGrid}>
        {(["label_width_mm", "label_height_mm"] as const).map((key) => (
          <NumberInput
            key={key}
            id={key}
            label={key === "label_width_mm" ? "Width (mm)" : "Height (mm)"}
            min={20}
            max={300}
            value={values[key]}
            disabled={!canMutate || saving}
            onChange={(_, { value }) =>
              setValues((current) => ({ ...current, [key]: Number(value) }))
            }
          />
        ))}
      </div>
      {(
        [
          ["label_show_name", "Show name / bin position"],
          ["label_show_reference", "Show reference / bin code"],
          ["label_show_barcode", "Show barcode"],
          ["label_show_logo", "Show company logo"],
        ] as const
      ).map(([key, label]) => (
        <Checkbox
          key={key}
          id={key}
          labelText={label}
          checked={values[key]}
          disabled={!canMutate || saving}
          onChange={(_, { checked }) =>
            setValues((current) => ({ ...current, [key]: checked }))
          }
        />
      ))}
      {message ? (
        <InlineNotification
          title={error ? "Could not save" : "Saved"}
          subtitle={message}
          kind={error ? "error" : "success"}
          hideCloseButton
        />
      ) : null}
      <AdminSaveActions
        canMutate={canMutate}
        saving={saving}
        dirty={dirty}
        onSave={() => void save()}
        onDiscard={() => { drafts.set("labels"); setValues(saved); setMessage(null); }}
      />
    </Stack>
  );
}
