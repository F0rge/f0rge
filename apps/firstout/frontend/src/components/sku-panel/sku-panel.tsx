"use client";

import { Archive, ChevronLeft, ChevronRight, Close, Edit, Maximize, Minimize, Printer, Renew } from "@carbon/icons-react";
import { Button, InlineNotification, SkeletonPlaceholder, SkeletonText, Tag } from "@carbon/react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { usePathname, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState, type MouseEvent } from "react";
import { createPortal } from "react-dom";
import { LoadingRegion } from "@/components/page-loading";
import { WorkspaceBulkDialog } from "@/components/record-workspace/workspace-bulk-dialog";
import { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { breadcrumbsForPath } from "@/lib/breadcrumbs";
import { catalogueListKeys, getSkuOverview, type SkuOverview } from "@/lib/catalogue-lists";
import { canMutateCatalogue, canRaisePo, canReceive } from "@/lib/permissions";
import {
  addToPurchaseOrderHref,
  adjustStockHref,
  keysBelongToTarget,
  readSkuPanel,
  skuPanelPageLabel,
  skuPanelPosition,
  stepSkuId,
} from "@/lib/sku-panel";
import { printSkuLabels } from "@/lib/sku-label-print";
import { SKU_SECTION_NAMES, skuStatusTags, type SkuSectionId } from "@/lib/sku-summary";
import { refreshSku } from "./edit/shared";
import { useSkuPanel, type SkuPanelApi } from "./provider";
import { SKU_SECTIONS, SkuSectionStateContext, type SkuCardEditing, type SkuSectionLayout, type SkuSectionState } from "./sections";
import { SkuThumb } from "./sku-thumb";
import styles from "./sku-panel.module.css";

const ARCHIVED_NOTICE =
  "Restore before editing, selling or adding to a new order or kit. Stock and history remain; existing work and returns can finish. Restoring keeps the previous sales setting and does not publish online.";

/** Stock and Activity are derived, so they never edit; a kit is not bought in, so it has no Supply to edit. */
function editableSection(id: SkuSectionId, overview: SkuOverview): boolean {
  if (id === "stock" || id === "activity") return false;
  return id !== "supply" || !overview.is_kit;
}

function Sections({ overview, layout, state }: { overview: SkuOverview; layout: SkuSectionLayout; state: Omit<SkuSectionState, "layout" | "modeOf"> & { editingId: SkuSectionId | null } }) {
  const value = useMemo<SkuSectionState>(() => ({
    ...state,
    layout,
    // Cards edit only in the full view; the docked groups always read.
    modeOf: (id) => (layout === "full" && state.editingId === id ? "edit" : "read"),
  }), [state, layout]);
  const [first, ...rest] = SKU_SECTIONS;
  return (
    <SkuSectionStateContext.Provider value={value}>
      {layout === "panel" ? (
        SKU_SECTIONS.map(({ id, Component }) => <Component key={id} overview={overview} />)
      ) : (
        <div className={`${styles.record}${state.editingId === "overview" ? ` ${styles.recordEditingFacts}` : ""}`}>
          <first.Component overview={overview} />
          <div className={styles.cards}>{rest.map(({ id, Component }) => <Component key={id} overview={overview} />)}</div>
        </div>
      )}
    </SkuSectionStateContext.Provider>
  );
}

function Header({ overview, panel, id, full, pageLabel, onEdit, onLifecycle }: {
  overview: SkuOverview | undefined;
  panel: SkuPanelApi;
  id: string;
  full: boolean;
  pageLabel: string;
  onEdit: ((section: SkuSectionId) => void) | null;
  onLifecycle: ((action: "archive" | "restore") => void) | null;
}) {
  const { user } = useAuth();
  const [printError, setPrintError] = useState<string | null>(null);
  const ids = panel.context?.ids ?? [id];
  const position = skuPanelPosition(panel.context ?? { ids: [id], label: "" }, id, pageLabel);
  const sku = overview?.sku;
  // A real link for new tabs; a plain click asks about unsaved changes first. The destination
  // URL carries no panel parameters, so the page opens without the panel.
  const leaveTo = (href: string) => (event: MouseEvent<HTMLElement>) => {
    if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey) return;
    event.preventDefault();
    panel.navigate(href);
  };
  return (
    <div className={styles.header}>
      <div className={styles.crumbs}>
        <button type="button" className={styles.pageCrumb} onClick={panel.close} title={`Back to ${pageLabel}`}>{pageLabel}</button>
        <span className={styles.crumbSep} aria-hidden="true">›</span>
        <span className={styles.chip}>
          <span className={styles.position} aria-live="polite">{position}</span>
          <button type="button" aria-label="Previous SKU" disabled={!stepSkuId(ids, id, -1)} onClick={() => panel.step(-1)}><ChevronLeft /></button>
          <button type="button" aria-label="Next SKU" disabled={!stepSkuId(ids, id, 1)} onClick={() => panel.step(1)}><ChevronRight /></button>
        </span>
        <span className={styles.spacer} />
        {full ? (
          <Button kind="ghost" size="sm" hasIconOnly renderIcon={Minimize} iconDescription="Back to side panel (Esc)" tooltipPosition="bottom" onClick={() => panel.setView("docked")} />
        ) : (
          <Button kind="ghost" size="sm" hasIconOnly renderIcon={Maximize} iconDescription="Open full view (Enter)" tooltipPosition="bottom" onClick={() => panel.setView("full")} />
        )}
        <Button kind="ghost" size="sm" hasIconOnly renderIcon={Close} iconDescription="Close" tooltipPosition="bottom" tooltipAlignment="end" onClick={panel.close} />
      </div>
      {sku ? (
        <div className={styles.identity}>
          <SkuThumb sku={sku} className={styles.headThumb} />
          <div>
            <h2 className={styles.title}>{sku.name}</h2>
            <div className={styles.meta}>
              <code>{sku.our_ref}</code>
              {skuStatusTags(sku).map((tag) => <Tag key={tag.label} size="sm" type={tag.type}>{tag.label}</Tag>)}
            </div>
          </div>
        </div>
      ) : (
        <div className={styles.identity} aria-hidden="true">
          <SkeletonPlaceholder className={styles.headThumb} />
          <div className={styles.grow}><SkeletonText heading width="70%" /><SkeletonText width="40%" /></div>
        </div>
      )}
      {sku && (
        <div className={styles.quick}>
          {onEdit && <Button kind="ghost" size="sm" renderIcon={Edit} onClick={() => onEdit("pricing")}>Edit price</Button>}
          <Button kind="ghost" size="sm" renderIcon={Printer} onClick={() => {
            setPrintError(null);
            printSkuLabels([sku]).catch((err: unknown) => setPrintError(err instanceof Error ? err.message : "Could not print label."));
          }}>Print label</Button>
          {canRaisePo(user) && !sku.is_archived && !overview?.is_kit && (
            <Button kind="ghost" size="sm" href={addToPurchaseOrderHref(sku.id)} onClick={leaveTo(addToPurchaseOrderHref(sku.id))}>
              Add to purchase order
            </Button>
          )}
          {canReceive(user) && !overview?.is_kit && (
            <Button kind="ghost" size="sm" href={adjustStockHref(sku.id)} onClick={leaveTo(adjustStockHref(sku.id))}>
              Adjust stock
            </Button>
          )}
          {onLifecycle && (
            sku.is_archived
              ? <Button kind="ghost" size="sm" renderIcon={Renew} onClick={() => onLifecycle("restore")}>Restore</Button>
              : <Button kind="ghost" size="sm" renderIcon={Archive} onClick={() => onLifecycle("archive")}>Archive</Button>
          )}
        </div>
      )}
      {printError && <InlineNotification kind="error" lowContrast title="Label not printed" subtitle={printError} onCloseButtonClick={() => setPrintError(null)} />}
    </div>
  );
}

function PanelLoading() {
  return (
    <LoadingRegion label="Loading SKU…" className="firstout-loading-motion">
      <div className={styles.loadingBody}>
        {SKU_SECTIONS.slice(0, 4).map(({ id }) => <SkeletonText key={id} paragraph lineCount={2} />)}
      </div>
    </LoadingRegion>
  );
}

const FIRST_FIELD = "input:not([type=hidden]):not([disabled]), select:not([disabled]), textarea:not([disabled]), button:not([disabled])";

/** The shell-level SKU panel: docked beside the page, or grown to the full view. Reads `?sku` and `&skuView`. */
export function SkuPanel() {
  const params = useSearchParams();
  const pathname = usePathname();
  const panel = useSkuPanel();
  const client = useQueryClient();
  const { user } = useAuth();
  const state = readSkuPanel(params);
  const element = useRef<HTMLElement>(null);
  // Keep the last SKU rendered while the panel slides away.
  const [shown, setShown] = useState<string | null>(state?.id ?? null);
  if (state && state.id !== shown) setShown(state.id);
  const id = state?.id ?? shown;
  const view = state?.view ?? "closed";
  const [openGroups, setOpenGroups] = useState<ReadonlySet<SkuSectionId>>(() => new Set(["overview", "stock"]));
  const [lifecycle, setLifecycle] = useState<"archive" | "restore" | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const overview = useQuery({
    queryKey: catalogueListKeys.skuOverview(id ?? ""),
    queryFn: ({ signal }) => getSkuOverview(id ?? "", signal),
    enabled: Boolean(state),
  });
  const data = overview.data;

  // Per-card editing: one card at a time, full view only, for this SKU only.
  const [editing, setEditing] = useState<{ section: SkuSectionId; skuId: string } | null>(null);
  const [asking, setAsking] = useState<(() => void) | null>(null);
  const dirty = useRef(false);
  const editingRef = useRef(editing);
  const askingRef = useRef(asking);
  useEffect(() => { editingRef.current = editing; askingRef.current = asking; });
  const editingId = editing && editing.skuId === id && view === "full" ? editing.section : null;
  const canEdit = Boolean(data && canMutateCatalogue(user) && !data.sku.is_archived);

  const finish = useCallback(() => {
    dirty.current = false;
    editingRef.current = null;
    setEditing(null);
    setAsking(null);
  }, []);
  // Leaving the card with changes asks first; a clean card just closes.
  const leaveCard = useCallback((proceed: () => void): boolean => {
    if (!editingRef.current) return false;
    if (!dirty.current) { finish(); return false; }
    setAsking(() => proceed);
    return true;
  }, [finish]);
  const setLeaveGuard = panel?.setLeaveGuard;
  useEffect(() => {
    if (!setLeaveGuard) return;
    setLeaveGuard(leaveCard);
    return () => setLeaveGuard(null);
  }, [setLeaveGuard, leaveCard]);

  const startEditing = useCallback((section: SkuSectionId) => {
    if (!id) return;
    const start = () => { dirty.current = false; setAsking(null); setEditing({ section, skuId: id }); };
    if (leaveCard(start)) return;
    start();
    if (view !== "full") panel?.setView("full");
  }, [id, leaveCard, panel, view]);

  // Another SKU, or leaving the full view by any route (even the browser's Back), ends the edit.
  // Editing may start while still docked, a moment before the URL says full, so only a move away
  // from full counts. Adjusted during render, as React recommends for state that follows props.
  const [seen, setSeen] = useState({ id, view });
  if (seen.id !== id || seen.view !== view) {
    setSeen({ id, view });
    if (editing && (editing.skuId !== id || (seen.view === "full" && view !== "full"))) {
      setEditing(null);
      setAsking(null);
    }
  }

  const cardEditing = useMemo<SkuCardEditing>(() => ({
    setDirty: (next) => { dirty.current = next; },
    finish,
    asking: Boolean(asking),
    keepEditing: () => setAsking(null),
    discard: () => {
      const proceed = askingRef.current;
      finish();
      proceed?.();
    },
  }), [asking, finish]);

  const sectionState = useMemo(() => ({
    isOpen: (section: SkuSectionId) => openGroups.has(section),
    setOpen: (section: SkuSectionId, open: boolean) => setOpenGroups((current) => {
      const next = new Set(current);
      if (open) next.add(section);
      else next.delete(section);
      return next;
    }),
    editingId,
    editing: cardEditing,
    renderActions: canEdit ? (section: SkuSectionId, item: SkuOverview) => {
      if (!editableSection(section, item) || editingId === section) return null;
      const name = SKU_SECTION_NAMES[section];
      return (
        <button
          type="button"
          className={styles.editLink}
          aria-label={`Edit ${name}`}
          onClick={(event) => {
            // Inside a <summary>: do not toggle the group.
            event.preventDefault();
            event.stopPropagation();
            startEditing(section);
          }}
        >
          <Edit aria-hidden="true" /> Edit
        </button>
      );
    } : undefined,
  }), [openGroups, editingId, cardEditing, canEdit, startEditing]);

  // Focus: the editing card's first field, the discard question, or the panel itself.
  const opened = Boolean(state);
  useEffect(() => {
    if (!opened) return;
    const root = element.current;
    if (view === "full" && editingId) {
      const card = root?.querySelector<HTMLElement>(`[data-sku-section="${editingId}"]`);
      const target = asking ? card?.querySelector<HTMLElement>("[data-keep-editing]") : card?.querySelector<HTMLElement>(`form ${FIRST_FIELD}`);
      requestAnimationFrame(() => {
        card?.scrollIntoView({ block: "nearest" });
        target?.focus({ preventScroll: true });
      });
      return;
    }
    root?.focus({ preventScroll: true });
  }, [opened, view, editingId, asking]);

  // In the full view the page underneath stays mounted but out of reach of Tab and screen readers.
  useEffect(() => {
    const main = document.getElementById("main-content");
    if (!main || view !== "full") return;
    main.inert = true;
    return () => { main.inert = false; };
  }, [view]);

  useEffect(() => {
    if (!opened || !panel) return;
    function onKeyDown(event: KeyboardEvent) {
      if (event.defaultPrevented || event.metaKey || event.ctrlKey || event.altKey || !panel) return;
      if (document.querySelector(".cds--modal.is-visible")) return;
      const target = event.target as HTMLElement | null;
      // Esc while a card edits, even from a field: close the question, ask about changes, or leave a clean card.
      if (event.key === "Escape" && view === "full" && editingRef.current && !target?.closest("[aria-expanded=true]")) {
        event.preventDefault();
        if (askingRef.current) setAsking(null);
        else if (dirty.current) panel.back();
        else finish();
        return;
      }
      if (keysBelongToTarget(target)) return;
      if (event.key === "Escape") {
        event.preventDefault();
        panel.back();
      } else if (event.key === "ArrowDown" || event.key === "ArrowUp") {
        event.preventDefault();
        panel.step(event.key === "ArrowDown" ? 1 : -1);
      } else if (event.key === "Enter" && view === "docked" && (target === element.current || target === document.body)) {
        event.preventDefault();
        panel.setView("full");
      }
    }
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [opened, panel, view, finish]);

  if (!panel || !id) return null;
  const pageLabel = skuPanelPageLabel(breadcrumbsForPath(pathname));
  const error = overview.error;
  const body = (layout: SkuSectionLayout) => (
    <>
      {data?.sku.is_archived && (
        <InlineNotification kind="info" lowContrast hideCloseButton title="Archived SKU" subtitle={ARCHIVED_NOTICE} className={styles.notice} />
      )}
      {notice && (layout === "full") === (view === "full") && (
        <InlineNotification kind="success" lowContrast title="Done" subtitle={notice} className={styles.notice} onCloseButtonClick={() => setNotice(null)} />
      )}
      {data ? <Sections overview={data} layout={layout} state={sectionState} /> : error ? (
        <div className={styles.notice}>
          <InlineNotification
            kind="error"
            lowContrast
            hideCloseButton
            title={error instanceof ApiError && error.status === 404 ? "SKU not found" : "Could not load this SKU"}
            subtitle={error.message}
          />
          <Button kind="tertiary" size="sm" onClick={() => void overview.refetch()}>Retry</Button>
        </div>
      ) : <PanelLoading />}
    </>
  );
  return (
    <aside
      ref={element}
      className={styles.panel}
      data-sku-panel={view}
      aria-label={data ? `SKU ${data.sku.our_ref}` : "SKU"}
      aria-hidden={view === "closed" || undefined}
      inert={view === "closed"}
      tabIndex={-1}
    >
      <Header
        overview={data}
        panel={panel}
        id={id}
        full={view === "full"}
        pageLabel={pageLabel}
        onEdit={canEdit ? startEditing : null}
        onLifecycle={data && canMutateCatalogue(user) ? (action) => { setNotice(null); setLifecycle(action); } : null}
      />
      <div className={styles.body} hidden={view === "full"}>{body("panel")}</div>
      <div className={`${styles.body} ${styles.fullBody}`} hidden={view !== "full"}>{body("full")}</div>
      <p className={styles.footer} aria-hidden="true">
        <span><kbd>↑</kbd> <kbd>↓</kbd> step through</span>
        {view === "docked" && <span><kbd>Enter</kbd> full view</span>}
        <span><kbd>Esc</kbd> {view === "full" ? "back to side panel" : "close"}</span>
      </p>
      {lifecycle && data && createPortal(
        // Portalled: inside the panel the modal would sit in its stacking context, under the header.
        <WorkspaceBulkDialog
          resource="skus"
          operation={{ action: lifecycle, label: lifecycle === "restore" ? "Restore" : "Archive", count: 1, selection: { ids: [data.sku.id] } }}
          fields={[]}
          onClose={() => setLifecycle(null)}
          onComplete={(message) => { setNotice(message); void refreshSku(client, data.sku.id); }}
        />,
        document.body,
      )}
    </aside>
  );
}
