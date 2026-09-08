import { describe, expect, it } from "vitest";

import { showViewCanvasButton } from "./nia-canvas-nav";

describe("showViewCanvasButton", () => {
  it("hides View Canvas on /canvas including trailing slash, query, and hash", () => {
    expect(showViewCanvasButton("/canvas")).toBe(false);
    expect(showViewCanvasButton("/canvas/")).toBe(false);
    expect(showViewCanvasButton("/canvas?foo=1")).toBe(false);
    expect(showViewCanvasButton("/canvas#sheet")).toBe(false);
    expect(showViewCanvasButton("/canvas/?foo=1#sheet")).toBe(false);
  });

  it("shows View Canvas on every other path", () => {
    expect(showViewCanvasButton("/")).toBe(true);
    expect(showViewCanvasButton("/invoices")).toBe(true);
    expect(showViewCanvasButton("/canvas/archive")).toBe(true);
    expect(showViewCanvasButton("")).toBe(true);
  });
});
