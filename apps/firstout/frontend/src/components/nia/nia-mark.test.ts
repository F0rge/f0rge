import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { NiaMark } from "./nia-mark";

describe("NiaMark", () => {
  it("renders a geometric N squircle, not the Smile N paths", () => {
    const html = renderToStaticMarkup(createElement(NiaMark, { size: 20 }));
    expect(html).toContain("firstout-nia-mark");
    expect(html).toContain("viewBox=\"0 0 24 24\"");
    expect(html).toContain("rx=\"6\"");
    expect(html).toContain("#4589ff");
    expect(html).toContain("#8a3ffc");
    expect(html).not.toContain("feGaussianBlur");
    expect(html).not.toContain("M 7.9 12.75 C 10.25 17.25");
  });
});
