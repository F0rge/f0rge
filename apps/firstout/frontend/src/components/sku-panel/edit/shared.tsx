"use client";

import { Button, InlineNotification, Layer } from "@carbon/react";
import { useQueryClient, type QueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState, type FormEvent, type ReactNode } from "react";
import type { Sku } from "@/lib/api";
import { cardSaveFailure, formChanged, type CardErrors } from "@/lib/catalogue-editor";
import { catalogueListKeys, type SkuOverview } from "@/lib/catalogue-lists";
import { queryKeys } from "@/lib/queries";
import { SKU_SECTION_NAMES, type SkuSectionId } from "@/lib/sku-summary";
import { useSkuSection } from "../sections/section";
import styles from "../sku-panel.module.css";

/**
 * Refresh everything that shows this SKU after a save: the overview (awaited, so the card
 * returns to reading the new values), the catalogue table, the shared SKU list and the
 * managed lists whose counts change.
 */
export async function refreshSku(client: QueryClient, id: string, updated?: Sku) {
  if (updated) client.setQueryData<SkuOverview>(catalogueListKeys.skuOverview(id), (old) => old && { ...old, sku: updated });
  for (const queryKey of [["record-workspace"], queryKeys.skus, ["categories"], ["materials"], ["sku-bom", id], ["cost-audit", id], ["search"]]) {
    void client.invalidateQueries({ queryKey });
  }
  await client.invalidateQueries({ queryKey: catalogueListKeys.skuOverview(id) });
}

/**
 * One card's draft: starts from `initial()` when the card enters edit mode, reports whether it
 * changed, and runs the save. A failed save keeps the draft and maps the server's refusal onto fields.
 */
export function useCardDraft<T>(skuId: string, initial: () => T) {
  const { editing } = useSkuSection();
  const client = useQueryClient();
  const [start] = useState(initial);
  const [draft, setDraft] = useState(start);
  const [fieldErrors, setFieldErrors] = useState<CardErrors>({});
  const [failure, setFailure] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const busy = useRef(false);
  const dirty = formChanged(start, draft);
  const setDirty = editing?.setDirty;
  useEffect(() => setDirty?.(dirty), [dirty, setDirty]);

  function update(patch: Partial<T>, clear: readonly string[] = Object.keys(patch)) {
    setDraft((current) => ({ ...current, ...patch }));
    if (clear.some((key) => fieldErrors[key])) {
      setFieldErrors((current) => Object.fromEntries(Object.entries(current).filter(([key]) => !clear.includes(key))));
    }
  }

  /** `localErrors` stop the save before any request; `task` returns the updated SKU when it has one. */
  async function save(localErrors: CardErrors, task: () => Promise<Sku | void | null>) {
    if (busy.current) return;
    setFieldErrors(localErrors);
    if (Object.keys(localErrors).length) {
      setFailure("Check the highlighted fields.");
      return;
    }
    if (!dirty) {
      editing?.finish();
      return;
    }
    busy.current = true;
    setSaving(true);
    setFailure(null);
    try {
      const updated = await task();
      await refreshSku(client, skuId, updated ?? undefined);
      editing?.setDirty(false);
      editing?.finish();
    } catch (error) {
      const result = cardSaveFailure(error);
      setFieldErrors(result.fields);
      setFailure(result.message);
    } finally {
      busy.current = false;
      setSaving(false);
    }
  }

  return { draft, setDraft, update, dirty, errors: fieldErrors, failure, setFailure, saving, save };
}

/** The editing card's body: a form whose foot holds the failure, the discard question, Save and Cancel. */
export function CardForm({ id, saving, failure, onSave, children }: {
  id: SkuSectionId;
  saving: boolean;
  failure: string | null;
  onSave: () => void;
  children: ReactNode;
}) {
  const { editing } = useSkuSection();
  const name = SKU_SECTION_NAMES[id];
  return (
    <form
      className={styles.editForm}
      noValidate
      aria-label={`Edit ${name}`}
      onSubmit={(event: FormEvent) => { event.preventDefault(); onSave(); }}
    >
      {/* The card is a layer of its own, so its fields take the next field fill and stand out from it. */}
      <Layer className={styles.editForm}>{children}</Layer>
      <div className={styles.cardFoot}>
        {failure && (
          <InlineNotification kind="error" lowContrast hideCloseButton title={`${name} not saved`} subtitle={failure} className={styles.footNotice} />
        )}
        {editing?.asking && (
          <div className={styles.discardBar} role="group" aria-label="Unsaved changes">
            <span>Discard changes to {name}?</span>
            <Button kind="ghost" size="sm" data-keep-editing onClick={editing.keepEditing}>Keep editing</Button>
            <Button kind="danger--tertiary" size="sm" onClick={editing.discard}>Discard</Button>
          </div>
        )}
        <div className={styles.footButtons}>
          <Button kind="ghost" size="sm" disabled={saving} onClick={() => editing?.finish()}>Cancel</Button>
          <Button kind="primary" size="sm" type="submit" disabled={saving}>{saving ? "Saving…" : "Save"}</Button>
        </div>
      </div>
    </form>
  );
}
