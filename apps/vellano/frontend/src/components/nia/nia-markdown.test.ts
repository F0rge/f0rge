import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { NiaMarkdown } from "./nia-markdown";

describe("NiaMarkdown", () => {
  it("renders bold, lists, and inline code without raw markers", () => {
    const html = renderToStaticMarkup(
      createElement(NiaMarkdown, {
        text: "**Required:**\n\n1. Name\n2. Design\n\nUse `VEL-SOF-0123`.",
      }),
    );
    expect(html).toContain("<strong>");
    expect(html).toContain("Required:");
    expect(html).not.toContain("**Required:**");
    expect(html).toContain("<ol>");
    expect(html).toContain("<code>");
    expect(html).not.toContain("`VEL-SOF-0123`");
  });

  it("does not render raw HTML", () => {
    const html = renderToStaticMarkup(
      createElement(NiaMarkdown, { text: '<img src="x" onerror="alert(1)" />' }),
    );
    expect(html).not.toContain("<img");
  });
});
