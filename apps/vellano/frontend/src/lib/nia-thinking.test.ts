import { describe, expect, it } from "vitest";

import {
  formatNiaWorkingTitle,
  niaThinkingBody,
  niaThinkingSummary,
  niaThinkingTitle,
  niaWorkingElapsedSeconds,
  showNiaWorkingRow,
} from "./nia-thinking";

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

describe("working-row timer helper", () => {
  it("floors elapsed milliseconds to seconds", () => {
    expect(niaWorkingElapsedSeconds(1_000, 13_400)).toBe(12);
    expect(niaWorkingElapsedSeconds(5_000, 4_000)).toBe(0);
  });

  it("formats Working Ns", () => {
    expect(formatNiaWorkingTitle(0)).toBe("Working 0s");
    expect(formatNiaWorkingTitle(12)).toBe("Working 12s");
  });

  it("uses Working Ns as the title while waiting", () => {
    expect(
      niaThinkingTitle({
        streaming: true,
        answerStarted: false,
        elapsedSeconds: 12,
        toolNames: [],
        hasReasoning: false,
      }),
    ).toBe("Working 12s");
  });

  it("keeps Working Ns even when a tool is in flight", () => {
    expect(
      niaThinkingTitle({
        streaming: true,
        answerStarted: false,
        elapsedSeconds: 4,
        toolNames: ["create_sku"],
        hasReasoning: false,
      }),
    ).toBe("Working 4s");
  });

  it("leaves the body empty while waiting with no tools", () => {
    expect(niaThinkingBody({ thinkingText: "", toolNames: [], waiting: true })).toBe("");
  });

  it("shows the last tool line while waiting", () => {
    expect(
      niaThinkingBody({
        thinkingText: "",
        toolNames: ["create_sku"],
        waiting: true,
      }),
    ).toBe("Calling create_sku…");
  });
});
