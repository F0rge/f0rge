import { describe, expect, it } from "vitest";

import { headingMatches, resolveTourTarget, routeMatches } from "./tour-navigation";
import type { TourStepDefinition } from "./tour-steps";

describe("tour navigation", () => {
  it("treats home as an exact path", () => {
    expect(routeMatches("/", "/")).toBe(true);
    expect(routeMatches("/catalogue", "/")).toBe(false);
    expect(routeMatches("/invoices/abc", "/invoices")).toBe(true);
    expect(routeMatches("/invoice", "/invoices")).toBe(false);
  });

  function element(text: string | null = null): Element {
    return { nodeType: 1, textContent: text } as unknown as Element;
  }

  function step(
    partial: Partial<TourStepDefinition> & Pick<TourStepDefinition, "id" | "target">,
  ): TourStepDefinition {
    return { title: partial.id, content: "step", ...partial };
  }

  it("spotlights the catalogue heading when the page is empty of products", () => {
    const heading = element("Catalogue");
    const found = resolveTourTarget(
      step({ id: "catalogue", target: "#main-content h1", heading: "Catalogue", route: "/catalogue" }),
      (selector) => (selector === "#main-content h1" ? heading : null),
    );
    expect(found).toBe(heading);
  });

  it("returns null when the catalogue heading is missing instead of the page body", () => {
    const body = element("app");
    const found = resolveTourTarget(
      step({ id: "catalogue", target: "#main-content h1", heading: "Catalogue", route: "/catalogue" }),
      (selector) => (selector === "body" ? body : null),
    );
    expect(found).toBeNull();
  });

  it("returns null when a spotlight selector is not in the document", () => {
    const heading = element("Home");
    const found = resolveTourTarget(
      step({
        id: "home-actions",
        target: "[data-tour='home-actions']",
        heading: "Home",
        route: "/",
      }),
      (selector) => (selector === "#main-content h1" ? heading : null),
    );
    expect(found).toBeNull();
  });

  it("matches page headings loosely", () => {
    expect(headingMatches("Customers CRM", "Customers")).toBe(true);
    expect(headingMatches("  Bank   reconciliation ", "bank reconciliation")).toBe(true);
    expect(headingMatches("Till", "Settings")).toBe(false);
    expect(headingMatches(null, "Home")).toBe(false);
  });
});
