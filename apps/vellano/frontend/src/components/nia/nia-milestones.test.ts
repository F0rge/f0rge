import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { NiaMilestoneList } from "./nia-thinking";

describe("NiaMilestoneList", () => {
  it("renders live milestone labels without emoji chrome", () => {
    const html = renderToStaticMarkup(
      createElement(NiaMilestoneList, {
        labels: ["Looking up overdue invoices", "  Checking stock  "],
      }),
    );
    expect(html).toContain("Looking up overdue invoices");
    expect(html).toContain("Checking stock");
    expect(html).toContain("vellano-nia-dock__milestone");
    expect(html).not.toContain("Working");
  });

  it("renders nothing when there are no labels", () => {
    expect(renderToStaticMarkup(createElement(NiaMilestoneList, { labels: ["  "] }))).toBe("");
  });
});
