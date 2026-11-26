"use client";

import { ChevronLeft, ChevronRight, Close, Edit, Maximize, Minimize, Printer } from "@carbon/icons-react";
import { Button, InlineNotification, SkeletonPlaceholder, SkeletonText, Tag } from "@carbon/react";
import { useQuery } from "@tanstack/react-query";
import { usePathname, useSearchParams } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import { LoadingRegion } from "@/components/page-loading";
import { ApiError, canMutateCatalogue } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { breadcrumbsForPath } from "@/lib/breadcrumbs";
import { catalogueListKeys, getSkuOverview, type SkuOverview } from "@/lib/catalogue-lists";
import { keysBelongToTarget, readSkuPanel, skuPanelPosition, stepSkuId } from "@/lib/sku-panel";
import { printSkuLabels } from "@/lib/sku-label-print";
import { skuStatusTags, type SkuSectionId } from "@/lib/sku-summary";
import { useSkuPanel, type SkuPanelApi } from "./provider";
import { SKU_SECTIONS, SkuSectionStateContext, type SkuSectionLayout, type SkuSectionState } from "./sections";
import { SkuThumb } from "./sku-thumb";
import styles from "./sku-panel.module.css";

const ARCHIVED_NOTICE =
  "Restore before editing, selling or adding to a new order or kit. Stock and history remain; existing work and returns can finish. Restoring keeps the previous sales setting and does not publish online.";

function Sections({ overview, layout, state }: { overview: SkuOverview; layout: SkuSectionLayout; state: Omit<SkuSectionState, "layout"> }) {
  const value = useMemo(() => ({ ...state, layout }), [state, layout]);
  const [first, ...rest] = SKU_SECTIONS;
  return (
    <SkuSectionStateContext.Provider value={value}>
      {layout === "panel" ? (
        SKU_SECTIONS.map(({ id, Component }) => <Component key={id} overview={overview} />)
      ) : (
        <div className={styles.record}>
          <first.Component overview={overview} />
          <div className={styles.cards}>{rest.map(({ id, Component }) => <Component key={id} overview={overview} />)}</div>
        </div>
      )}
    </SkuSectionStateContext.Provider>
  );
}

function Header({ overview, panel, id, full, pageLabel }: {
  overview: SkuOverview | undefined;
  panel: SkuPanelApi;
  id: string;
  full: boolean;
  pageLabel: string;
}) {
  const { user } = useAuth();
  const [printError, setPrintError] = useState<string | null>(null);
  const ids = panel.context?.ids ?? [id];
  const position = skuPanelPosition(panel.context ?? { ids: [id], label: "" }, id);
  const sku = overview?.sku;
  const canEdit = canMutateCatalogue(user);
  const editAction = sku && !sku.is_archived ? panel.editAction : null;
  return (
    <div className={styles.header}>
      <div className={styles.crumbs}>
        {full && (
          <>
            <button type="button" className={styles.pageCrumb} onClick={panel.close} title={`Back to ${pageLabel}`}>{pageLabel}</button>
            <span className={styles.crumbSep} aria-hidden="true">›</span>
          </>
        )}
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
          {editAction ? (
            <>
              <Button kind="ghost" size="sm" renderIcon={Edit} onClick={() => editAction(sku, {})}>Edit SKU</Button>
              <Button kind="ghost" size="sm" onClick={() => editAction(sku, { pricing: true })}>Edit price</Button>
            </>
          ) : canEdit && (
            // ponytail: until per-card editing lands, edits happen on the existing SKU page.
            <Button kind="ghost" size="sm" renderIcon={Edit} href={`/catalogue/${sku.id}`}>Edit SKU</Button>
          )}
          <Button kind="ghost" size="sm" renderIcon={Printer} onClick={() => {
            setPrintError(null);
            printSkuLabels([sku]).catch((err: unknown) => setPrintError(err instanceof Error ? err.message : "Could not print label."));
          }}>Print label</Button>
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

/** The shell-level SKU panel: docked beside the page, or grown to the full view. Reads `?sku` and `&skuView`. */
export function SkuPanel() {
  const params = useSearchParams();
  const pathname = usePathname();
  const panel = useSkuPanel();
  const state = readSkuPanel(params);
  const element = useRef<HTMLElement>(null);
  // Keep the last SKU rendered while the panel slides away.
  const [shown, setShown] = useState<string | null>(state?.id ?? null);
  if (state && state.id !== shown) setShown(state.id);
  const id = state?.id ?? shown;
  const view = state?.view ?? "closed";
  const [openGroups, setOpenGroups] = useState<ReadonlySet<SkuSectionId>>(() => new Set(["overview", "stock"]));
  const overview = useQuery({
    queryKey: catalogueListKeys.skuOverview(id ?? ""),
    queryFn: ({ signal }) => getSkuOverview(id ?? "", signal),
    enabled: Boolean(state),
  });

  const sectionState = useMemo<Omit<SkuSectionState, "layout">>(() => ({
    isOpen: (section) => openGroups.has(section),
    setOpen: (section, open) => setOpenGroups((current) => {
      const next = new Set(current);
      if (open) next.add(section);
      else next.delete(section);
      return next;
    }),
    modeOf: () => "read",
  }), [openGroups]);

  // Focus moves into the panel when it opens and when it changes size, so Esc and ↑ ↓ work at once.
  const opened = Boolean(state);
  useEffect(() => {
    if (opened) element.current?.focus({ preventScroll: true });
  }, [opened, view]);

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
      if (document.querySelector(".cds--modal.is-visible") || keysBelongToTarget(event.target as HTMLElement | null)) return;
      const target = event.target as HTMLElement | null;
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
  }, [opened, panel, view]);

  if (!panel || !id) return null;
  const crumbs = breadcrumbsForPath(pathname);
  const pageLabel = crumbs.at(-1)?.label ?? "Home";
  const data = overview.data;
  const error = overview.error;
  const body = (layout: SkuSectionLayout) => (
    <>
      {data?.sku.is_archived && (
        <InlineNotification kind="info" lowContrast hideCloseButton title="Archived SKU" subtitle={ARCHIVED_NOTICE} className={styles.notice} />
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
      <Header overview={data} panel={panel} id={id} full={view === "full"} pageLabel={pageLabel} />
      <div className={styles.body} hidden={view === "full"}>{body("panel")}</div>
      <div className={`${styles.body} ${styles.fullBody}`} hidden={view !== "full"}>{body("full")}</div>
      <p className={styles.footer} aria-hidden="true">
        <span><kbd>↑</kbd> <kbd>↓</kbd> step through</span>
        {view === "docked" && <span><kbd>Enter</kbd> full view</span>}
        <span><kbd>Esc</kbd> {view === "full" ? "back to side panel" : "close"}</span>
      </p>
    </aside>
  );
}
