"use client";

import { useRouter } from "next/navigation";
import { createContext, useCallback, useContext, useMemo, useRef, useState, type ReactNode } from "react";
import {
  contextFor,
  readSkuPanel,
  skuPanelBack,
  skuPanelSearch,
  stepSkuId,
  type SkuPanelContext,
  type SkuPanelState,
  type SkuPanelView,
} from "@/lib/sku-panel";

/**
 * Asked before the panel leaves the SKU or the full view. Returns true when it blocked the move
 * (a card has unsaved changes); it then calls `proceed` itself if the user discards them.
 */
export type SkuLeaveGuard = (proceed: () => void) => boolean;

export interface SkuPanelApi {
  /** Dock the panel on the current page. `context` is the ordered list ↑ ↓ step through. */
  open: (id: string, context?: SkuPanelContext | null) => void;
  /** Change docked ↔ full for the SKU already shown. */
  setView: (view: SkuPanelView) => void;
  /** Esc: full → docked → closed. */
  back: () => void;
  close: () => void;
  /** Move to the previous (-1) or next (+1) SKU in the context. */
  step: (delta: number) => void;
  context: SkuPanelContext | null;
  /** Replace the context's ids and label, but only while `key` still owns it (for example a new page of catalogue rows). */
  refreshContext: (key: string, ids: readonly string[], label: string) => void;
  /** Leave the page for `href`, asking first about unsaved card changes. */
  navigate: (href: string) => void;
  /** The full view registers this while a card is being edited. */
  setLeaveGuard: (guard: SkuLeaveGuard | null) => void;
}

const SkuPanelContextValue = createContext<SkuPanelApi | null>(null);

function currentState(): SkuPanelState | null {
  return readSkuPanel(new URLSearchParams(window.location.search));
}

function focusable(element: Element | null): element is HTMLElement {
  return element instanceof HTMLElement && element !== document.body && document.contains(element);
}

/** Shell-level owner of the SKU panel: URL state (`?sku`, `&skuView=full`) and the stepping context. */
export function SkuPanelProvider({ children }: { children: ReactNode }) {
  const router = useRouter();
  const [context, setContext] = useState<SkuPanelContext | null>(null);
  const leaveGuard = useRef<SkuLeaveGuard | null>(null);
  const returnFocus = useRef<HTMLElement | null>(null);

  const go = useCallback(
    (state: SkuPanelState | null) => {
      const search = skuPanelSearch(window.location.search, state);
      // replace, not push: the page underneath keeps its history entry, state and scroll.
      router.replace(`${window.location.pathname}${search ? `?${search}` : ""}${window.location.hash}`, { scroll: false });
    },
    [router],
  );

  // Every way out of the SKU goes through here, so unsaved card changes are never lost silently.
  const guarded = useCallback((action: () => void) => {
    if (!leaveGuard.current?.(action)) action();
  }, []);

  const close = useCallback(() => guarded(() => {
    if (!currentState()) return;
    go(null);
    const target = returnFocus.current;
    returnFocus.current = null;
    requestAnimationFrame(() => {
      const main = document.getElementById("main-content");
      (focusable(target) ? target : main)?.focus({ preventScroll: true });
    });
  }), [go, guarded]);

  const open = useCallback((id: string, next?: SkuPanelContext | null) => guarded(() => {
    const state = currentState();
    if (!state) {
      const active = document.activeElement;
      // Opened from header search: return to the page on close, not to the search box.
      returnFocus.current = focusable(active) && !active.closest("[role=search], [data-sku-panel]") ? active : null;
    }
    setContext(contextFor(id, next));
    go({ id, view: state?.view ?? "docked" });
  }), [go, guarded]);

  const setView = useCallback((view: SkuPanelView) => guarded(() => {
    const state = currentState();
    if (state && state.view !== view) go({ ...state, view });
  }), [go, guarded]);

  const back = useCallback(() => guarded(() => {
    const next = skuPanelBack(currentState());
    if (next) go(next);
    else close();
  }), [close, go, guarded]);

  const step = useCallback((delta: number) => guarded(() => {
    const state = currentState();
    if (!state) return;
    const id = stepSkuId(context?.ids ?? [state.id], state.id, delta);
    if (id) go({ ...state, id });
  }), [context, go, guarded]);

  const navigate = useCallback((href: string) => guarded(() => router.push(href)), [guarded, router]);

  const refreshContext = useCallback((key: string, ids: readonly string[], label: string) => {
    setContext((current) =>
      current?.key === key && (current.label !== label || current.ids.join() !== ids.join()) ? { ids, label, key } : current);
  }, []);

  const setLeaveGuard = useCallback((guard: SkuLeaveGuard | null) => { leaveGuard.current = guard; }, []);

  const api = useMemo<SkuPanelApi>(
    () => ({ open, setView, back, close, step, context, refreshContext, navigate, setLeaveGuard }),
    [open, setView, back, close, step, context, refreshContext, navigate, setLeaveGuard],
  );

  return <SkuPanelContextValue.Provider value={api}>{children}</SkuPanelContextValue.Provider>;
}

/** The panel API, or null outside the back-office shell (links then navigate normally). */
export function useSkuPanel(): SkuPanelApi | null {
  return useContext(SkuPanelContextValue);
}
