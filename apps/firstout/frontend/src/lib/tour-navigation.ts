import type { Step } from "react-joyride";

import { setSideNavExpanded } from "@/lib/side-nav-preference";
import type { TourStepDefinition } from "@/lib/tour-steps";
import { getNarrowViewportSnapshot } from "@/lib/viewport";

export function routeMatches(pathname: string, route: string, exact = false): boolean {
  if (exact || route === "/") {
    return pathname === route;
  }
  return pathname === route || pathname.startsWith(`${route}/`);
}

export function headingMatches(text: string | null | undefined, expected: string): boolean {
  const normalized = (text ?? "").replace(/\s+/g, " ").trim().toLowerCase();
  return normalized.includes(expected.trim().toLowerCase());
}

export function waitUntil(predicate: () => boolean, timeoutMs: number): Promise<boolean> {
  return new Promise((resolve) => {
    const started = Date.now();
    const check = () => {
      if (predicate()) {
        resolve(true);
        return;
      }
      if (Date.now() - started >= timeoutMs) {
        resolve(false);
        return;
      }
      window.setTimeout(check, 50);
    };
    check();
  });
}

function elementReady(match: HTMLElement): boolean {
  const modal = match.closest(".cds--modal");
  if (modal instanceof HTMLElement && !modal.classList.contains("is-visible")) {
    return false;
  }
  if (match.closest("[hidden]")) {
    return false;
  }
  return match.getClientRects().length > 0;
}

function findTarget(selector: string): HTMLElement | null {
  for (const node of document.querySelectorAll(selector)) {
    if (node instanceof HTMLElement && elementReady(node)) {
      return node;
    }
  }
  return null;
}

function resolveTarget(step: TourStepDefinition): HTMLElement {
  if (step.target !== "body") {
    return findTarget(step.target) ?? document.body;
  }
  return document.body;
}

export async function prepareTourStep(
  step: TourStepDefinition,
  navigate: (route: string) => void,
): Promise<void> {
  if (step.expandNav) {
    setSideNavExpanded(true);
  } else if (getNarrowViewportSnapshot()) {
    setSideNavExpanded(false);
  }

  if (step.route && !routeMatches(window.location.pathname, step.route, Boolean(step.exact))) {
    navigate(step.route);
    await waitUntil(
      () => routeMatches(window.location.pathname, step.route ?? "", Boolean(step.exact)),
      12000,
    );
  }

  if (step.target !== "body" && step.open && !findTarget(step.target)) {
    const opener = step.open ? findTarget(step.open) ?? document.querySelector(step.open) : null;
    if (opener instanceof HTMLElement) {
      opener.click();
    }
  }

  if (step.target !== "body") {
    await waitUntil(() => findTarget(step.target) instanceof HTMLElement, 8000);
  }

  if (step.expandNav) {
    await waitUntil(() => {
      const nav = document.querySelector(".firstout-side-nav");
      return nav instanceof HTMLElement && nav.classList.contains("cds--side-nav--expanded");
    }, 2000);
  }
}

export function buildJoyrideSteps(
  definitions: TourStepDefinition[],
  navigate: (route: string) => void,
): Step[] {
  return definitions.map((step) => ({
    id: step.id,
    title: step.title,
    content: step.content,
    placement: step.placement ?? "bottom",
    isFixed: step.isFixed ?? false,
    target: step.target === "body" ? "body" : () => resolveTarget(step),
    before: async () => {
      await prepareTourStep(step, navigate);
    },
  }));
}
