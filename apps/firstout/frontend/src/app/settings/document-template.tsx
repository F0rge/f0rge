"use client";

import {
  Accordion,
  AccordionItem,
  Button,
  Checkbox,
  InlineNotification,
  RadioButton,
  RadioButtonGroup,
  Select,
  SelectItem,
  Slider,
  Stack,
  TextArea,
  TextInput,
  Toggle,
} from "@carbon/react";
import { ArrowDown, ArrowUp, Reset } from "@carbon/icons-react";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import {
  ApiError,
  getDocumentTemplate,
  getSettings,
  listCreditNotes,
  listInvoices,
  listPayments,
  listQuotes,
  previewDocumentTemplate,
  saveDocumentTemplate,
} from "@/lib/api";
import { AdminSaveActions } from "@/components/admin-save-actions";
import {
  DOCUMENT_KINDS,
  HEX_COLOUR,
  SECTION_LABELS,
  moveSection,
  templateProblem,
  type DocumentKind,
  type DocumentTemplate,
} from "@/lib/document-template";
import styles from "./settings.module.css";

const SWATCHES: [string, string][] = [
  ["#161616", "Black"],
  ["#0f62fe", "Blue"],
  ["#198038", "Green"],
  ["#8a3ffc", "Purple"],
  ["#9f1853", "Magenta"],
  ["#b28600", "Gold"],
];
const PREVIEW_DELAY_MS = 400;

type SampleOption = { id: string; label: string };

async function recentDocuments(kind: DocumentKind): Promise<SampleOption[]> {
  const params = { limit: 20 };
  switch (kind) {
    case "invoice":
      return (await listInvoices(params)).items.map((row) => ({ id: row.id, label: `${row.invoice_number} · ${row.customer_name}` }));
    case "quote":
      return (await listQuotes(params)).items.map((row) => ({ id: row.id, label: `${row.quote_number} · ${row.customer_name}` }));
    case "credit_note":
      return (await listCreditNotes(params)).items.map((row) => ({ id: row.id, label: `${row.credit_note_number} · ${row.invoice_number}` }));
    case "receipt":
      return (await listPayments(params)).items.map((row) => ({
        id: row.id,
        label: [row.payment_number, row.party_name].filter(Boolean).join(" · "),
      }));
  }
}

/** Live PDF of the draft, refreshed a moment after the last change. */
function usePreview(template: DocumentTemplate | null, kind: DocumentKind, sampleId: string, enabled: boolean) {
  const [url, setUrl] = useState<string | null>(null);
  // The blob URL on screen; each new one revokes it, and so does leaving the page.
  const shown = useRef<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const request = enabled && template && !templateProblem(template) ? JSON.stringify({ template, kind, sample_id: sampleId || null }) : null;

  useEffect(() => {
    if (!request) return;
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      setLoading(true);
      previewDocumentTemplate(JSON.parse(request), controller.signal)
        .then((blob) => {
          if (shown.current) URL.revokeObjectURL(shown.current);
          shown.current = URL.createObjectURL(blob);
          setUrl(shown.current);
          setError(null);
        })
        .catch((err: unknown) => {
          if (controller.signal.aborted) return;
          setError(err instanceof ApiError ? err.message : "Could not render the preview.");
        })
        .finally(() => {
          if (!controller.signal.aborted) setLoading(false);
        });
    }, PREVIEW_DELAY_MS);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [request]);

  useEffect(() => () => {
    if (shown.current) URL.revokeObjectURL(shown.current);
  }, []);

  return { url, error, loading };
}

export function DocumentTemplateSettings({ canMutate }: { canMutate: boolean }) {
  const [saved, setSaved] = useState<DocumentTemplate | null>(null);
  const [defaults, setDefaults] = useState<DocumentTemplate | null>(null);
  const [draft, setDraft] = useState<DocumentTemplate | null>(null);
  const [hasLogo, setHasLogo] = useState(false);
  const [tradingName, setTradingName] = useState<string | null>(null);
  const [kind, setKind] = useState<DocumentKind>("invoice");
  const [sampleId, setSampleId] = useState("");
  const [samples, setSamples] = useState<SampleOption[]>([]);
  const [hex, setHex] = useState("");
  const [loadError, setLoadError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<{ kind: "success" | "error"; text: string } | null>(null);
  const preview = usePreview(draft, kind, sampleId, canMutate);

  useEffect(() => {
    let cancelled = false;
    Promise.all([getDocumentTemplate(), getSettings()])
      .then(([response, settings]) => {
        if (cancelled) return;
        setSaved(response.template);
        setDefaults(response.defaults);
        setDraft(response.template);
        setHex(response.template.accent_colour);
        setHasLogo(settings.has_logo);
        setTradingName(settings.trading_name);
      })
      .catch((err: unknown) => {
        if (!cancelled) setLoadError(err instanceof ApiError ? err.message : "Failed to load the document template");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!canMutate) return;
    let cancelled = false;
    setSamples([]);
    recentDocuments(kind)
      .then((rows) => {
        if (!cancelled) setSamples(rows);
      })
      .catch(() => {
        // Sample data still previews; the picker just lists no documents.
      });
    return () => {
      cancelled = true;
    };
  }, [canMutate, kind]);

  if (loadError) {
    return <InlineNotification kind="error" title="Documents" subtitle={loadError} hideCloseButton lowContrast />;
  }
  if (!draft || !saved || !defaults) {
    return <p className="cds--type-body-01">Loading the document template…</p>;
  }

  const dirty = JSON.stringify(draft) !== JSON.stringify(saved);
  const problem = templateProblem(draft);
  const disabled = !canMutate || saving;
  const wording = draft.wording[kind];
  const kindLabel = DOCUMENT_KINDS.find((entry) => entry.value === kind)?.label ?? "";
  const edit = (patch: Partial<DocumentTemplate>) => setDraft({ ...draft, ...patch });

  function replace(next: DocumentTemplate) {
    setDraft(next);
    setHex(next.accent_colour);
    setMessage(null);
  }

  async function save() {
    if (!draft || problem) return;
    setSaving(true);
    setMessage(null);
    try {
      const response = await saveDocumentTemplate(draft);
      setSaved(response.template);
      replace(response.template);
      setMessage({ kind: "success", text: "Template saved. Documents print with it from now on." });
    } catch (err: unknown) {
      setMessage({ kind: "error", text: err instanceof ApiError ? err.message : "Failed to save the template" });
    } finally {
      setSaving(false);
    }
  }

  const controls = (
    <Accordion>
      <AccordionItem title="Logo" open>
        <Stack gap={5}>
          <p className="cds--type-helper-text-01">
            {hasLogo ? "Documents use your company logo." : "No logo yet. Documents print without one until you upload it."}{" "}
            <Link href="/settings?tab=company">Upload or change the logo under Company</Link>
          </p>
          <RadioButtonGroup
            legendText="Position"
            name="logo-position"
            valueSelected={draft.logo_position}
            disabled={disabled}
            onChange={(value) => edit({ logo_position: value as DocumentTemplate["logo_position"] })}
          >
            <RadioButton id="logo-left" labelText="Left" value="left" />
            <RadioButton id="logo-centre" labelText="Centre" value="centre" />
            <RadioButton id="logo-right" labelText="Right" value="right" />
          </RadioButtonGroup>
          <Slider
            id="logo-height"
            labelText="Height (px)"
            min={40}
            max={120}
            step={4}
            value={draft.logo_height}
            disabled={disabled}
            hideTextInput
            onChange={({ value }) => edit({ logo_height: value })}
          />
        </Stack>
      </AccordionItem>
      <AccordionItem title="Brand" open>
        <Stack gap={5}>
          <fieldset className="cds--fieldset">
            <legend className="cds--label">Accent colour</legend>
            <div className={styles.swatches}>
              {SWATCHES.map(([colour, name]) => (
                <button
                  key={colour}
                  type="button"
                  className={styles.swatch}
                  style={{ background: colour }}
                  aria-label={name}
                  aria-pressed={draft.accent_colour === colour}
                  title={`${name} ${colour}`}
                  disabled={disabled}
                  onClick={() => replace({ ...draft, accent_colour: colour })}
                />
              ))}
            </div>
          </fieldset>
          <TextInput
            id="accent-hex"
            labelText="Hex value"
            size="sm"
            value={hex}
            disabled={disabled}
            invalid={!HEX_COLOUR.test(hex)}
            invalidText="Enter a colour like #0f62fe."
            helperText="Colours the title and the table header. Pick a dark shade so it prints clearly."
            onChange={(event) => {
              setHex(event.target.value);
              edit({ accent_colour: event.target.value.toLowerCase() });
            }}
          />
          <Select
            id="template-font"
            labelText="Font"
            value={draft.font}
            disabled={disabled}
            onChange={(event) => edit({ font: event.target.value as DocumentTemplate["font"] })}
          >
            <SelectItem value="sans" text="Sans serif (Helvetica)" />
            <SelectItem value="serif" text="Serif (Times)" />
            <SelectItem value="mono" text="Monospace (Courier)" />
          </Select>
          <RadioButtonGroup
            legendText="Density"
            name="template-density"
            valueSelected={draft.density}
            disabled={disabled}
            onChange={(value) => edit({ density: value as DocumentTemplate["density"] })}
          >
            <RadioButton id="density-comfortable" labelText="Comfortable" value="comfortable" />
            <RadioButton id="density-compact" labelText="Compact" value="compact" />
          </RadioButtonGroup>
          <RadioButtonGroup
            legendText="Table header"
            name="template-table-header"
            valueSelected={draft.table_header}
            disabled={disabled}
            onChange={(value) => edit({ table_header: value as DocumentTemplate["table_header"] })}
          >
            <RadioButton id="table-band" labelText="Shaded band" value="band" />
            <RadioButton id="table-lines" labelText="Rule line" value="lines" />
            <RadioButton id="table-solid" labelText="Solid colour" value="solid" />
          </RadioButtonGroup>
        </Stack>
      </AccordionItem>
      <AccordionItem title="Sections" open>
        <Stack gap={3}>
          <p className="cds--type-helper-text-01">Show or hide sections and set their order.</p>
          {draft.sections.map((section, index) => (
            <div key={section.key} className={styles.sectionRow}>
              <span>{SECTION_LABELS[section.key]}</span>
              <Button
                kind="ghost"
                size="sm"
                hasIconOnly
                renderIcon={ArrowUp}
                iconDescription={`Move ${SECTION_LABELS[section.key]} up`}
                disabled={disabled || index === 0}
                onClick={() => edit(moveSection(draft, index, -1))}
              />
              <Button
                kind="ghost"
                size="sm"
                hasIconOnly
                renderIcon={ArrowDown}
                iconDescription={`Move ${SECTION_LABELS[section.key]} down`}
                disabled={disabled || index === draft.sections.length - 1}
                onClick={() => edit(moveSection(draft, index, 1))}
              />
              <Toggle
                id={`section-${section.key}`}
                labelText={`Show ${SECTION_LABELS[section.key]}`}
                hideLabel
                size="sm"
                toggled={section.visible}
                disabled={disabled}
                onToggle={(visible) =>
                  edit({ sections: draft.sections.map((entry, at) => (at === index ? { ...entry, visible } : entry)) })
                }
              />
            </div>
          ))}
        </Stack>
      </AccordionItem>
      <AccordionItem title="Line item columns">
        <Stack gap={3}>
          {(
            [
              ["sku_ref", "SKU reference under the description"],
              ["discount", "Discount column (only when a line has a discount)"],
              ["line_vat", "VAT per line"],
            ] as const
          ).map(([key, label]) => (
            <Checkbox
              key={key}
              id={`column-${key}`}
              labelText={label}
              checked={draft.columns[key]}
              disabled={disabled}
              onChange={(_, { checked }) => edit({ columns: { ...draft.columns, [key]: checked } })}
            />
          ))}
        </Stack>
      </AccordionItem>
      <AccordionItem title={`Wording: ${kindLabel}`}>
        <Stack gap={5}>
          <p className="cds--type-helper-text-01">Each document type has its own wording. Switch the type above the preview to edit another one.</p>
          {(
            [
              ["title", "Title"],
              ["number_label", "Number label"],
            ] as const
          ).map(([key, label]) => (
            <TextInput
              key={key}
              id={`wording-${key}`}
              labelText={label}
              value={wording[key]}
              disabled={disabled}
              invalid={!wording[key].trim()}
              invalidText={`Enter a ${label.toLowerCase()}.`}
              onChange={(event) =>
                edit({ wording: { ...draft.wording, [kind]: { ...wording, [key]: event.target.value } } })
              }
            />
          ))}
          <TextArea
            id="wording-terms"
            labelText="Terms"
            rows={4}
            value={wording.terms}
            disabled={disabled}
            helperText="Leave it empty to leave terms off this document type."
            onChange={(event) => edit({ wording: { ...draft.wording, [kind]: { ...wording, terms: event.target.value } } })}
          />
        </Stack>
      </AccordionItem>
      <AccordionItem title="Footer">
        <TextArea
          id="template-footer"
          labelText="Footer text"
          rows={3}
          maxCount={500}
          enableCounter
          value={draft.footer}
          disabled={disabled}
          helperText="Printed at the foot of every page."
          onChange={(event) => edit({ footer: event.target.value })}
        />
      </AccordionItem>
      <AccordionItem title="Extras">
        <Stack gap={5}>
          <Toggle
            id="template-trading-name"
            labelText="Show trading name"
            labelA="Hidden"
            labelB="Shown"
            toggled={draft.show_trading_name}
            disabled={disabled}
            onToggle={(show) => edit({ show_trading_name: show })}
          />
          {draft.show_trading_name && !tradingName ? (
            <p className="cds--type-helper-text-01">
              No trading name yet. <Link href="/settings?tab=company">Add it under Company</Link>
            </p>
          ) : null}
          <Toggle
            id="template-paid-stamp"
            labelText="Paid and On statement stamps on invoices and receipts"
            labelA="Off"
            labelB="On"
            toggled={draft.paid_stamp}
            disabled={disabled}
            onToggle={(on) => edit({ paid_stamp: on })}
          />
        </Stack>
      </AccordionItem>
    </Accordion>
  );

  return (
    <Stack gap={5}>
      <div className={styles.templateToolbar}>
        <p className="cds--type-helper-text-01">One layout for tax invoices, quotes, credit notes and receipts.</p>
        {canMutate ? (
          <Button kind="ghost" renderIcon={Reset} disabled={saving} onClick={() => replace(defaults)}>
            Reset to default
          </Button>
        ) : null}
      </div>
      {message ? (
        <InlineNotification
          kind={message.kind}
          title={message.kind === "success" ? "Saved" : "Could not save"}
          subtitle={message.text}
          hideCloseButton
          lowContrast
        />
      ) : null}
      <div className={styles.templateLayout}>
        {controls}
        <Stack gap={4} className={styles.templatePreview}>
          <div className={styles.formGrid}>
            <Select
              id="template-kind"
              labelText="Document type"
              value={kind}
              onChange={(event) => {
                setKind(event.target.value as DocumentKind);
                setSampleId("");
              }}
            >
              {DOCUMENT_KINDS.map((entry) => (
                <SelectItem key={entry.value} value={entry.value} text={entry.label} />
              ))}
            </Select>
            <Select
              id="template-sample"
              labelText="Preview with"
              value={sampleId}
              disabled={!canMutate}
              onChange={(event) => setSampleId(event.target.value)}
            >
              <SelectItem value="" text="Sample data" />
              {samples.map((entry) => (
                <SelectItem key={entry.id} value={entry.id} text={entry.label} />
              ))}
            </Select>
          </div>
          {!canMutate ? (
            <InlineNotification kind="info" title="Preview" subtitle="Only people who can change settings can preview the template." hideCloseButton lowContrast />
          ) : problem ? (
            <InlineNotification kind="warning" title="Preview paused" subtitle={problem} hideCloseButton lowContrast />
          ) : preview.error ? (
            <InlineNotification kind="error" title="Preview" subtitle={preview.error} hideCloseButton lowContrast />
          ) : null}
          {preview.url ? (
            <iframe
              className={styles.templateFrame}
              src={`${preview.url}#toolbar=0&navpanes=0`}
              title={`${kindLabel} preview`}
              aria-busy={preview.loading}
            />
          ) : canMutate ? (
            <p className="cds--type-body-01" role="status">Rendering the preview…</p>
          ) : null}
        </Stack>
      </div>
      <AdminSaveActions
        canMutate={canMutate}
        saving={saving}
        dirty={dirty}
        saveDisabled={!!problem}
        onSave={() => void save()}
        onDiscard={() => {
          replace(saved);
        }}
      />
    </Stack>
  );
}
