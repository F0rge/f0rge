import { describe, expect, it } from "vitest";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { BeforeYouPay } from "./before-you-pay";
import { IMPORTANT_TERMS, IMPORTANT_TERMS_PURPOSE, policyPage } from "@/lib/customer-policies";

describe("Before you pay", () => {
  it("shows the same important terms as the terms page and links to the full terms", () => {
    const html = renderToStaticMarkup(createElement(BeforeYouPay));
    const notice = policyPage(null, "terms").blocks.find((block) => block.type === "notice" && block.text.startsWith("Please read these points before you pay"));
    expect(IMPORTANT_TERMS.length).toBeGreaterThan(0);
    for (const point of [IMPORTANT_TERMS_PURPOSE, ...IMPORTANT_TERMS]) {
      expect(html).toContain(point.replaceAll("'", "&#x27;"));
      expect(notice?.text).toContain(point);
    }
    expect(html).toContain('href="/policies/terms"');
    expect(html).toContain("By continuing you accept our terms of sale.");
  });
});
