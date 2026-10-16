import type { Step } from "react-joyride";

import { setSideNavExpanded } from "@/lib/side-nav-preference";
import type { TourStepDefinition } from "@/lib/tour-steps";
import { getNarrowViewportSnapshot } from "@/lib/viewport";

export function routeMatches(pathname: string, route: string): boolean {
  if (route === "/") {
    return pathname === "/";
  }
  return pathname === route || pathname.startsWith(`${route}/`);
}

export function headingMatches(text: string | null | undefined, expected: string): boolean {
  const normalized = (text ?? "").replace(/\s+/g, " ").trim().toLowerCase();
  return normalized.includes(expected.trim().toLowerCase());
}

/** Bumped when the tour is dismissed so an in-flight step cannot navigate afterwards. */
let navigationEpoch = 0;

export function cancelTourNavigation(): void {
  navigationEpoch += 1;
}

/** Drop a Joyride mask that survived the tour closing, and release its focus. */
export function releaseTourBlockers(): void {
  if (typeof document === "undefined") {
    return;
  }
  const portal = document.getElementById("react-joyride-portal");
  portal?.querySelectorAll(".react-joyride__overlay, .react-joyride__floater").forEach((node) => {
    node.remove();
  });
  const active = document.activeElement;
  if (active instanceof HTMLElement && portal?.contains(active)) {
    active.blur();
  }
}

export function waitUntil(
  predicate: () => boolean,
  timeoutMs: number,
  isCancelled?: () => boolean,
): Promise<boolean> {
  return new Promise((resolve) => {
    const started = Date.now();
    const check = () => {
      if (isCancelled?.()) {
        resolve(false);
        return;
      }
      if (predicate()) {
        resolve(true);
        return;
      }
      if (Date.now() - started >= timeoutMs) {
        resolve(false);
        return;
      }
      globalThis.setTimeout(check, 50);
    };
    check();
  });
}

function asHtmlElement(value: Element | null): HTMLElement | null {
  if (!value) {
    return null;
  }
  if (typeof HTMLElement !== "undefined" && value instanceof HTMLElement) {
    return value;
  }
  if (value.nodeType === 1) {
    return value as HTMLElement;
  }
  return null;
}

/**
 * Spotlight only an element that is actually on screen.
 * A missing heading or selector returns null so Joyride skips the step
 * instead of spotlighting `document.body` and blocking the whole page.
 */
export function resolveTourTarget(
  step: TourStepDefinition,
  query: (selector: string) => Element | null,
): HTMLElement | null {
  if (step.target === "body") {
    return asHtmlElement(query("body"));
  }

  const heading = asHtmlElement(query("#main-content h1"));
  const headingOk = !step.heading || headingMatches(heading?.textContent, step.heading);
  if (step.heading && headingOk && heading && (step.target === "#main-content h1" || step.target === "body")) {
    return heading;
  }
  if (step.heading && !headingOk && step.target === "#main-content h1") {
    return null;
  }

  if (!headingOk) {
    return null;
  }

  return asHtmlElement(query(step.target));
}

const HEADING_WAIT_MS = 4000;
const TARGET_WAIT_MS = 2000;
const NAV_WAIT_MS = 1500;

export async function prepareTourStep(
  step: TourStepDefinition,
  navigate: (route: string) => void,
): Promise<void> {
  const epoch = navigationEpoch;
  const stale = () => epoch !== navigationEpoch;

  if (stale()) {
    return;
  }

  if (step.expandNav) {
    setSideNavExpanded(true);
  } else if (getNarrowViewportSnapshot()) {
    setSideNavExpanded(false);
  }

  if (stale()) {
    return;
  }

  if (step.route && !routeMatches(window.location.pathname, step.route)) {
    navigate(step.route);
  }

  if (step.heading) {
    const headingReady = await waitUntil(
      () => headingMatches(document.querySelector("#main-content h1")?.textContent, step.heading ?? ""),
      HEADING_WAIT_MS,
      stale,
    );
    if (!headingReady || stale()) {
      return;
    }
  }

  if (step.target !== "body") {
    const targetReady = await waitUntil(
      () => document.querySelector(step.target) instanceof Element,
      TARGET_WAIT_MS,
      stale,
    );
    if (!targetReady || stale()) {
      return;
    }
  }

  if (step.expandNav) {
    await waitUntil(() => {
      const nav = document.querySelector(".firstout-side-nav");
      return nav instanceof Element && nav.classList.contains("cds--side-nav--expanded");
    }, NAV_WAIT_MS, stale);
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
    target: step.target === "body" ? "body" : () => resolveTourTarget(step, (selector) => document.querySelector(selector)),
    before: async () => {
      await prepareTourStep(step, navigate);
    },
  }));
}
