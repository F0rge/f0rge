import { describe, expect, it } from "vitest";

import { niaThinkingSummary, showNiaWorkingRow } from "./nia-thinking";

describe("nia thinking helpers", () => {
  it("shows a working row only while waiting for the first token", () => {
    expect(showNiaWorkingRow(true, "")).toBe(true);
    expect(showNiaWorkingRow(true, "Nia")).toBe(false);
  });

  it("summarises the last tool after the answer starts", () => {
    expect(
      niaThinkingSummary({
        toolNames: ["create_sku"],
        hasReasoning: false,
        answerStarted: true,
      }),
    ).toBe("create_sku");
  });

  it("uses Thought for a few seconds when no tool name is available", () => {
    expect(
      niaThinkingSummary({
        toolNames: [],
        hasReasoning: true,
        answerStarted: true,
      }),
    ).toBe("Thought for a few seconds");
  });
});
