import { describe, expect, it } from "vitest";

import { PAGE_TOURS, pageTourForPath } from "./tour-steps";

const MAX_COPY = 140;

describe("firstout page tours", () => {
  it("teaches the page task on real controls, with short copy", () => {
    const ids = PAGE_TOURS.map((tour) => tour.id);
    expect(new Set(ids).size).toBe(ids.length);

    const laybys = pageTourForPath("/laybys");
    expect(laybys?.id).toBe("laybys");
    expect(laybys?.steps.map((step) => step.target)).toEqual([
      "[data-tour='layby-new']",
      "#layby-customer",
      "#layby-sku-0",
      ".cds--modal.is-visible .cds--btn--primary",
    ]);

    const customers = pageTourForPath("/customers");
    expect(customers?.steps.map((step) => step.target)).toEqual([
      "[data-tour='customer-new']",
      "#create-customer-name",
      ".cds--modal.is-visible .cds--btn--primary",
    ]);

    expect(pageTourForPath("/stocktakes")?.steps.map((step) => step.target)).toContain(
      "#stocktake-category",
    );
    expect(pageTourForPath("/catalogue")?.id).toBe("catalogue");
    expect(pageTourForPath("/catalogue/new")?.id).toBe("catalogue-new");
    expect(pageTourForPath("/customers/abc")).toBeNull();
    expect(pageTourForPath("/laybys/abc")).toBeNull();

    for (const tour of PAGE_TOURS) {
      expect(tour.steps.length).toBeGreaterThan(0);
      expect(tour.steps.length).toBeLessThanOrEqual(6);
      const stepIds = tour.steps.map((step) => step.id);
      expect(new Set(stepIds).size).toBe(stepIds.length);
      for (const step of tour.steps) {
        expect(step.content.trim().length).toBeGreaterThan(8);
        expect(step.content.trim().length).toBeLessThanOrEqual(MAX_COPY);
        expect(step.target).not.toContain("h1");
        expect(step.target).not.toBe("#main-content");
        expect("heading" in step).toBe(false);
      }
    }
  });

  it("points the profile tour at the header question mark", () => {
    const profile = pageTourForPath("/profile");
    expect(profile?.steps.at(-1)?.target).toBe("[data-tour='header-page-tour']");
    expect(profile?.steps.at(-1)?.content.toLowerCase()).toContain("question mark");
  });
});
