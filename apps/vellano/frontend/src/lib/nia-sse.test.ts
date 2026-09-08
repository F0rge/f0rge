import { describe, expect, it } from "vitest";

import { consumeNiaSse, milestoneLabelFromValue, parseNiaSseLine, peekNiaSseType } from "./nia-sse";
import { showNiaWorkingRow } from "./nia-thinking";

/**
 * Captured from ag-ui-protocol 0.1.22 EventEncoder.encode
 * (see apps/vellano/backend/tests/test_nia_sse.py).
 */
const ENCODED_TEXT_MESSAGE_CONTENT =
  'data: {"type":"TEXT_MESSAGE_CONTENT","messageId":"msg_1","delta":"Hello"}';
const ENCODED_TOOL_CALL_START =
  'data: {"type":"TOOL_CALL_START","toolCallId":"call_1","toolCallName":"create_sku"}';
const ENCODED_REASONING_CONTENT =
  'data: {"type":"REASONING_MESSAGE_CONTENT","messageId":"think_1","delta":"hmm"}';

describe("parseNiaSseLine", () => {
  it("maps TEXT_MESSAGE_CONTENT to answer tokens", () => {
    const event = parseNiaSseLine('data: {"type":"TEXT_MESSAGE_CONTENT","delta":"Hello"}');
    expect(event).toEqual({ kind: "text", delta: "Hello" });
  });

  it("maps a real EventEncoder TEXT_MESSAGE_CONTENT line", () => {
    expect(parseNiaSseLine(ENCODED_TEXT_MESSAGE_CONTENT)).toEqual({
      kind: "text",
      delta: "Hello",
    });
  });

  it("maps camelCase TextMessageContent to answer tokens", () => {
    const event = parseNiaSseLine('data: {"type":"TextMessageContent","delta":"Hello"}');
    expect(event).toEqual({ kind: "text", delta: "Hello" });
  });

  it("maps text-delta to answer tokens", () => {
    const event = parseNiaSseLine('data: {"type":"text-delta","delta":"Hi"}');
    expect(event).toEqual({ kind: "text", delta: "Hi" });
  });

  it("reads delta nested under event", () => {
    const event = parseNiaSseLine(
      'data: {"event":{"type":"TextMessageContent","delta":"Nested"}}',
    );
    expect(event).toEqual({ kind: "text", delta: "Nested" });
  });

  it("maps REASONING_MESSAGE_CONTENT to thinking", () => {
    const event = parseNiaSseLine('data: {"type":"REASONING_MESSAGE_CONTENT","delta":"hmm"}');
    expect(event).toEqual({ kind: "thinking", delta: "hmm" });
  });

  it("maps a real EventEncoder reasoning line", () => {
    expect(parseNiaSseLine(ENCODED_REASONING_CONTENT)).toEqual({
      kind: "thinking",
      delta: "hmm",
    });
  });

  it("maps TOOL_CALL_START to a tool name", () => {
    const event = parseNiaSseLine(
      'data: {"type":"TOOL_CALL_START","toolCallName":"create_sku"}',
    );
    expect(event).toEqual({ kind: "tool_start", name: "create_sku" });
  });

  it("maps a real EventEncoder TOOL_CALL_START line", () => {
    expect(parseNiaSseLine(ENCODED_TOOL_CALL_START)).toEqual({
      kind: "tool_start",
      name: "create_sku",
    });
  });

  it("does not treat TOOL_CALL_ARGS deltas as answer text", () => {
    const event = parseNiaSseLine(
      'data: {"type":"TOOL_CALL_ARGS","delta":"{\\"our_ref\\":\\"X\\"}"}',
    );
    expect(event).toBeNull();
  });

  it("peeks lifecycle types without treating them as tokens", () => {
    const line = 'data: {"type":"RUN_STARTED","threadId":"t","runId":"r"}';
    expect(peekNiaSseType(line)).toBe("RUN_STARTED");
    expect(parseNiaSseLine(line)).toBeNull();
  });

  it("maps CUSTOM nia.milestone events to a progress label", () => {
    const event = parseNiaSseLine(
      'data: {"type":"CUSTOM","name":"nia.milestone","value":{"label":"Looking up overdue invoices"}}',
    );
    expect(event).toEqual({
      kind: "milestone",
      label: "Looking up overdue invoices",
    });
  });

  it("maps camelCase Custom events named milestone", () => {
    const event = parseNiaSseLine(
      'data: {"type":"Custom","name":"milestone","value":"Checking stock"}',
    );
    expect(event).toEqual({ kind: "milestone", label: "Checking stock" });
  });

  it("ignores CUSTOM events that are not milestones", () => {
    expect(
      parseNiaSseLine('data: {"type":"CUSTOM","name":"count","value":1}'),
    ).toBeNull();
  });
});

describe("consumeNiaSse", () => {
  it("dispatches answer tokens as each encoded chunk arrives", async () => {
    const tokens: string[] = [];
    const encoder = new TextEncoder();
    const stream = new ReadableStream({
      start(controller) {
        controller.enqueue(
          encoder.encode('data: {"type":"TEXT_MESSAGE_CONTENT","messageId":"msg_1","delta":"Hel"}\n\n'),
        );
        controller.enqueue(
          encoder.encode('data: {"type":"TextMessageContent","delta":"lo"}\n\n'),
        );
        controller.enqueue(
          encoder.encode('data: {"type":"TOOL_CALL_START","toolCallName":"create_sku"}\n\n'),
        );
        controller.close();
      },
    });
    const tools: string[] = [];
    await consumeNiaSse(
      new Response(stream, {
        status: 200,
        headers: { "content-type": "text/event-stream" },
      }),
      {
        onToken: (delta) => tokens.push(delta),
        onTool: (name) => tools.push(name),
      },
    );
    expect(tokens).toEqual(["Hel", "lo"]);
    expect(tools).toEqual(["create_sku"]);
  });

  it("dispatches milestone events as they arrive", async () => {
    const encoder = new TextEncoder();
    const stream = new ReadableStream({
      start(controller) {
        controller.enqueue(
          encoder.encode(
            'data: {"type":"CUSTOM","name":"nia.milestone","value":{"label":"Looking up overdue invoices"}}\n\n',
          ),
        );
        controller.enqueue(
          encoder.encode('data: {"type":"TEXT_MESSAGE_CONTENT","delta":"INV-0004"}\n\n'),
        );
        controller.close();
      },
    });
    const labels: string[] = [];
    const tokens: string[] = [];
    await consumeNiaSse(
      new Response(stream, {
        status: 200,
        headers: { "content-type": "text/event-stream" },
      }),
      {
        onToken: (delta) => tokens.push(delta),
        onMilestone: (label) => labels.push(label),
      },
    );
    expect(labels).toEqual(["Looking up overdue invoices"]);
    expect(tokens).toEqual(["INV-0004"]);
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

describe("milestoneLabelFromValue", () => {
  it("reads label, step, or a plain string", () => {
    expect(milestoneLabelFromValue({ label: " Checking stock " })).toBe("Checking stock");
    expect(milestoneLabelFromValue({ step: "Summing totals" })).toBe("Summing totals");
    expect(milestoneLabelFromValue("Looking up")).toBe("Looking up");
    expect(milestoneLabelFromValue({ progress: 0.5 })).toBeNull();
  });
});
