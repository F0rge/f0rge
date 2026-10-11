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

function pageHeading(): HTMLElement | null {
  const heading = document.querySelector("#main-content h1");
  return heading instanceof HTMLElement ? heading : null;
}

function resolveTarget(step: TourStepDefinition): HTMLElement {
  if (step.heading) {
    const heading = pageHeading();
    if (heading && headingMatches(heading.textContent, step.heading)) {
      return heading;
    }
  }
  if (step.target !== "body") {
    const match = document.querySelector(step.target);
    if (match instanceof HTMLElement) {
      return match;
    }
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

  if (step.route && !routeMatches(window.location.pathname, step.route)) {
    navigate(step.route);
  }

  if (step.heading) {
    await waitUntil(
      () => headingMatches(pageHeading()?.textContent, step.heading ?? ""),
      12000,
    );
  }

  if (step.target !== "body") {
    await waitUntil(() => document.querySelector(step.target) instanceof Element, 8000);
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
