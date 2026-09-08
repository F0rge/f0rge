import { describe, expect, it } from "vitest";

import {
  formatNiaWorkingTitle,
  niaReasoningToggleLabel,
  niaThinkingBody,
  niaThinkingSummary,
  niaThinkingTitle,
  niaWorkingElapsedSeconds,
  showNiaReasoningToggle,
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

  it("does not put Working Ns on the reasoning accordion title", () => {
    expect(
      niaThinkingTitle({
        streaming: true,
        answerStarted: false,
        elapsedSeconds: 12,
        toolNames: [],
        hasReasoning: false,
      }),
    ).toBe("Thinking");
  });

  it("summarises the in-flight tool instead of Working Ns", () => {
    expect(
      niaThinkingTitle({
        streaming: true,
        answerStarted: false,
        elapsedSeconds: 4,
        toolNames: ["create_sku"],
        hasReasoning: false,
      }),
    ).toBe("Calling create_sku…");
  });

  it("hides the reasoning accordion while the Working spinner is visible", () => {
    expect(showNiaReasoningToggle({ working: true, hasActivity: true })).toBe(false);
    expect(showNiaReasoningToggle({ working: false, hasActivity: true })).toBe(true);
    expect(showNiaReasoningToggle({ working: false, hasActivity: false })).toBe(false);
  });

  it("labels the accordion Show reasoning instead of Working Ns", () => {
    expect(
      niaReasoningToggleLabel({
        expanded: false,
        streaming: true,
        answerStarted: false,
      }),
    ).toBe("Show reasoning");
    expect(
      niaReasoningToggleLabel({
        expanded: true,
        streaming: false,
        answerStarted: true,
      }),
    ).toBe("Hide reasoning");
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
