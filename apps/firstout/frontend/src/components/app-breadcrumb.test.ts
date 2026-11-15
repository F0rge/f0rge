import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

let pathname = "/";
vi.mock("next/navigation", () => ({ usePathname: () => pathname }));
import { AppBreadcrumb } from "./app-breadcrumb";

describe("native Carbon breadcrumb rendering", () => {
  it("renders no breadcrumb landmark on single-level Home and Till", () => {
    for (const route of ["/", "/till"]) {
      pathname = route;
      expect(renderToStaticMarkup(createElement(AppBreadcrumb))).toBe("");
    }
  });
  it("exposes the current page and only links a real list ancestor", () => {
    pathname = "/purchase-orders/fixture-order";
    const html = renderToStaticMarkup(createElement(AppBreadcrumb));
    expect(html).toContain('aria-label="Breadcrumb"');
    expect(html).toContain('aria-current="page"');
    expect(html).toContain('href="/purchase-orders"');
    expect(html).not.toContain('href="#"');
    expect(html).not.toContain('aria-current="true"');
    expect(html).not.toContain("fixture-order");
  });
});
