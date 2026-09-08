import { afterEach, describe, expect, it, vi } from "vitest";

import { resetMainScroll } from "./reset-main-scroll";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("resetMainScroll", () => {
  it("scrolls window and #main-content to top", () => {
    const scrollTo = vi.fn();
    const main = { id: "main-content", scrollTop: 800 };
    const documentElement = { scrollTop: 400 };
    const body = { scrollTop: 200 };
    const doc = {
      documentElement,
      body,
      getElementById: (id: string) => (id === "main-content" ? main : null),
    };
    vi.stubGlobal("window", { scrollTo });
    vi.stubGlobal("document", doc);

    resetMainScroll();

    expect(scrollTo).toHaveBeenCalledWith(0, 0);
    expect(documentElement.scrollTop).toBe(0);
    expect(body.scrollTop).toBe(0);
    expect(main.scrollTop).toBe(0);
  });
});
