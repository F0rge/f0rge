"use client";

import { ChevronDown } from "@carbon/icons-react";
import { createContext, useContext, useId, type ReactNode } from "react";
import { SKU_SECTION_NAMES, type SkuSectionId } from "@/lib/sku-summary";
import type { SkuOverview } from "@/lib/catalogue-lists";
import styles from "../sku-panel.module.css";

/** "panel": collapsible groups in the docked panel. "full": the facts column and cards of the full view. */
export type SkuSectionLayout = "panel" | "full";
/** A full-view card is "edit" while its fields are inputs; everything else reads. */
export type SkuSectionMode = "read" | "edit";

/** What an editing card needs from the panel: report changes, finish, and the discard question. */
export interface SkuCardEditing {
  /** The card reports whether its draft differs from where it started. */
  setDirty: (dirty: boolean) => void;
  /** Leave edit mode (after Cancel or a successful save). */
  finish: () => void;
  /** Set while "Discard changes to …?" is showing for this card. */
  asking: boolean;
  keepEditing: () => void;
  discard: () => void;
}

export interface SkuSectionState {
  layout: SkuSectionLayout;
  isOpen: (id: SkuSectionId) => boolean;
  setOpen: (id: SkuSectionId, open: boolean) => void;
  /** Which card is in edit mode (only ever one, and only in the full view). */
  modeOf: (id: SkuSectionId) => SkuSectionMode;
  /** Controls for a section's heading (the Edit button); Save/Cancel live in the body. */
  renderActions?: (id: SkuSectionId, overview: SkuOverview) => ReactNode;
  editing?: SkuCardEditing;
}

export const SkuSectionStateContext = createContext<SkuSectionState>({
  layout: "panel",
  isOpen: () => true,
  setOpen: () => undefined,
  modeOf: () => "read",
});

export function useSkuSection() {
  return useContext(SkuSectionStateContext);
}

/** Every section receives the one overview response, and nothing else. */
export interface SkuSectionProps {
  overview: SkuOverview;
}

/**
 * The frame every section renders into: a <details> group in the panel (with a one-line
 * summary while closed), a card in the full view (Overview is the facts column).
 */
export function SkuSectionFrame({ id, overview, summary, note, children }: {
  id: SkuSectionId;
  overview: SkuOverview;
  summary: string;
  /** Small text beside the card heading in the full view ("All locations"). */
  note?: string;
  children: ReactNode;
}) {
  const state = useSkuSection();
  const headingId = useId();
  const name = SKU_SECTION_NAMES[id];
  const actions = state.renderActions?.(id, overview);
  if (state.layout === "panel") {
    const open = state.isOpen(id);
    // The Edit control sits beside the <summary>, not in it: a summary is already a button.
    return (
      <div className={styles.groupWrap} data-has-actions={actions ? "" : undefined}>
        <details className={styles.group} open={open} onToggle={(event) => {
          if (event.currentTarget.open !== open) state.setOpen(id, event.currentTarget.open);
        }}>
          <summary>
            <span className={styles.groupTitle}>{name}</span>
            <span className={styles.groupSummary}>{summary}</span>
            <ChevronDown className={styles.chevron} aria-hidden="true" />
          </summary>
          <div className={styles.groupBody}>{children}</div>
        </details>
        {actions && <span className={styles.groupActions}>{actions}</span>}
      </div>
    );
  }
  const editing = state.modeOf(id) === "edit";
  return (
    <section
      className={`${id === "overview" ? styles.facts : styles.card}${editing ? ` ${styles.editing}` : ""}`}
      aria-labelledby={headingId}
      data-sku-section={id}
    >
      <h3 id={headingId} className={styles.cardTitle}>
        {name}
        {note && <small>{note}</small>}
        {actions && <span className={styles.cardActions}>{actions}</span>}
      </h3>
      {children}
    </section>
  );
}

/** A definition list of label/value pairs. `wide` spans the row. */
export function Facts({ items }: { items: readonly (readonly [string, ReactNode, boolean?] | false | null)[] }) {
  return (
    <dl className={styles.kv}>
      {items.filter((item): item is readonly [string, ReactNode, boolean?] => Boolean(item)).map(([label, value, wide]) => (
        <div key={label} className={wide ? styles.wide : undefined}>
          <dt>{label}</dt>
          <dd>{value === null || value === undefined || value === "" ? "—" : value}</dd>
        </div>
      ))}
    </dl>
  );
}
