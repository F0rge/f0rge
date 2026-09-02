import { describe, expect, it } from "vitest";

import { parseNiaSseLine } from "./nia-sse";
import { showNiaWorkingRow } from "./nia-thinking";

describe("parseNiaSseLine", () => {
  it("maps TEXT_MESSAGE_CONTENT to answer tokens", () => {
    const event = parseNiaSseLine('data: {"type":"TEXT_MESSAGE_CONTENT","delta":"Hello"}');
    expect(event).toEqual({ kind: "text", delta: "Hello" });
  });

  it("maps REASONING_MESSAGE_CONTENT to thinking", () => {
    const event = parseNiaSseLine('data: {"type":"REASONING_MESSAGE_CONTENT","delta":"hmm"}');
    expect(event).toEqual({ kind: "thinking", delta: "hmm" });
  });

  it("maps TOOL_CALL_START to a tool name", () => {
    const event = parseNiaSseLine(
      'data: {"type":"TOOL_CALL_START","toolCallName":"create_sku"}',
    );
    expect(event).toEqual({ kind: "tool_start", name: "create_sku" });
  });

  it("does not treat TOOL_CALL_ARGS deltas as answer text", () => {
    const event = parseNiaSseLine(
      'data: {"type":"TOOL_CALL_ARGS","delta":"{\\"our_ref\\":\\"X\\"}"}',
    );
    expect(event).toBeNull();
  });
});

describe("showNiaWorkingRow", () => {
  it("is visible when streaming and there is no answer text yet", () => {
    expect(showNiaWorkingRow(true, "")).toBe(true);
    expect(showNiaWorkingRow(true, "  ")).toBe(true);
    expect(showNiaWorkingRow(true, "Hi")).toBe(false);
    expect(showNiaWorkingRow(false, "")).toBe(false);
  });
});
