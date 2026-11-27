/**
 * URL state and stepping for the shell-level SKU panel.
 *
 * `?sku=<id>` docks the panel on the current page; `&skuView=full` expands it.
 * Every other query parameter belongs to the page underneath and is kept as is.
 */

export type SkuPanelView = "docked" | "full";
export interface SkuPanelState {
  id: string;
  view: SkuPanelView;
}
/** The ordered list the panel steps through, and what it is called ("oslo", "Catalogue"). */
export interface SkuPanelContext {
  ids: readonly string[];
  label: string;
  /** Who owns the context, so a page can refresh its own list (for example a new page of rows). */
  key?: string;
}

export const SKU_PARAM = "sku";
export const SKU_VIEW_PARAM = "skuView";
const ID_PATTERN = /^[0-9a-fA-F-]{32,36}$/;

interface SearchValues {
  get: (key: string) => string | null;
}

export function readSkuPanel(params: SearchValues): SkuPanelState | null {
  const id = params.get(SKU_PARAM);
  if (!id || !ID_PATTERN.test(id)) return null;
  return { id, view: params.get(SKU_VIEW_PARAM) === "full" ? "full" : "docked" };
}

/** The query string (no leading "?") for `search` with the panel set to `state`, other params untouched. */
export function skuPanelSearch(search: string, state: SkuPanelState | null): string {
  const values = new URLSearchParams(search);
  values.delete(SKU_PARAM);
  values.delete(SKU_VIEW_PARAM);
  if (state) {
    values.set(SKU_PARAM, state.id);
    if (state.view === "full") values.set(SKU_VIEW_PARAM, "full");
  }
  return values.toString();
}

/** Carry the panel parameters from `current` onto a query string a page built for itself. */
export function withSkuPanelParams(next: string, current: SearchValues): string {
  return skuPanelSearch(next, readSkuPanel(current));
}

/** One level back: full → docked → closed. */
export function skuPanelBack(state: SkuPanelState | null): SkuPanelState | null {
  if (!state) return null;
  return state.view === "full" ? { ...state, view: "docked" } : null;
}

/** The id `delta` steps away in the context, or null at either end (no wrapping). */
export function stepSkuId(ids: readonly string[], current: string, delta: number): string | null {
  const index = ids.indexOf(current);
  if (index < 0) return null;
  return ids[index + delta] ?? null;
}

/**
 * "oslo · 2 of 5", or "Catalogue · not in this list" when the SKU left the list. The label is
 * left out when it only repeats the page the trail already names ("Catalogue › 2 of 25").
 */
export function skuPanelPosition(context: SkuPanelContext, id: string, pageLabel = ""): string {
  const index = context.ids.indexOf(id);
  const where = index < 0 ? "not in this list" : `${index + 1} of ${context.ids.length}`;
  const label = context.label.trim().toLowerCase() === pageLabel.trim().toLowerCase() ? "" : context.label;
  return label ? `${label} · ${where}` : where;
}

/** The page the panel sits on, named as the page calls itself (the catalogue's crumb says "Products"). */
export function skuPanelPageLabel(crumbs: readonly { label: string }[], pathname = "/"): string {
  const label = crumbs.at(-1)?.label;
  // ponytail: the few pages without a crumb, by hand; move to a per-route title map if more appear.
  if (!label) return pathname.startsWith("/till") ? "Till" : "Home";
  return label === "Products" ? "Catalogue" : label;
}

/** A context that always contains `id`: callers that pass none get the SKU on its own. */
export function contextFor(id: string, context?: SkuPanelContext | null): SkuPanelContext {
  if (context && context.ids.includes(id)) return context;
  return { ids: [id], label: context?.label ?? "", key: context?.key };
}

interface KeyTarget {
  tagName?: string;
  type?: string;
  isContentEditable?: boolean;
  closest?: (selector: string) => unknown;
}

const OWN_KEYS =
  "[role=combobox],[role=listbox],[role=menu],[role=menuitem],[role=option],[role=slider],[role=spinbutton],[role=tablist],[role=tab],[role=grid],[role=dialog],[role=alertdialog],.cds--modal,.cds--overflow-menu-options";

/**
 * True when the focused element handles its own keys: a text field, select, textarea,
 * contenteditable, or a Carbon widget (modal, menu, combobox, tabs). Shortcuts must not fire then.
 */
export function keysBelongToTarget(target: KeyTarget | null): boolean {
  if (!target) return false;
  const tag = (target.tagName ?? "").toUpperCase();
  if (tag === "TEXTAREA" || tag === "SELECT") return true;
  if (tag === "INPUT" && !["checkbox", "radio", "button", "submit", "reset"].includes((target.type ?? "text").toLowerCase())) return true;
  if (target.isContentEditable) return true;
  return Boolean(target.closest?.(OWN_KEYS));
}

/**
 * Prefill parameter for pages that start work on one SKU. Deliberately not `sku`, which is the
 * panel's own parameter: following a quick action must not dock the panel on the destination.
 */
export const PREFILL_SKU_PARAM = "prefill_sku";
export const addToPurchaseOrderHref = (id: string) => `/purchase-orders?new=1&${PREFILL_SKU_PARAM}=${encodeURIComponent(id)}`;
export const adjustStockHref = (id: string) => `/adjustments?${PREFILL_SKU_PARAM}=${encodeURIComponent(id)}`;
