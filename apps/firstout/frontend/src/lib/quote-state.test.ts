import { describe, expect, it } from "vitest";

import { defaultValidUntil, isQuoteOpen, quoteState } from "./quote-state";

describe("quote state", () => {
  it("reads open quotes past their date as expired and keeps closed statuses", () => {
    expect(quoteState({ status: "draft", valid_until: "2026-11-30" }, "2026-11-21")).toBe("open");
    expect(quoteState({ status: "sent", valid_until: "2026-11-20" }, "2026-11-21")).toBe("expired");
    expect(quoteState({ status: "draft", valid_until: null }, "2026-11-21")).toBe("open");
    expect(quoteState({ status: "converted", valid_until: "2026-11-20" }, "2026-11-21")).toBe("converted");
    expect(isQuoteOpen({ status: "converted" })).toBe(false);
    expect(isQuoteOpen({ status: "accepted" })).toBe(false);
    expect(isQuoteOpen({ status: "expired" })).toBe(true);
  });

  it("is valid for 14 days by default", () => {
    expect(defaultValidUntil("2026-11-21")).toBe("2026-12-05");
  });
});
