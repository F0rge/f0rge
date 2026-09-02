import { ApiError } from "./api";

type NiaErrorBody = {
  detail?: string | { msg?: string }[] | { code?: string; message?: string };
};

export function niaErrorMessageFromBody(body: NiaErrorBody, fallback: string): string {
  const detail = body.detail;
  if (typeof detail === "string") {
    return detail;
  }
  if (Array.isArray(detail) && detail[0]?.msg) {
    return detail[0].msg;
  }
  if (detail && typeof detail === "object" && "code" in detail) {
    const code = detail.code;
    if (code === "nia_llm_unconfigured") {
      return "Nia is not configured";
    }
    if (code === "nia_cap_exceeded") {
      return "Monthly Nia allowance used";
    }
    if (typeof detail.message === "string" && detail.message.trim()) {
      return detail.message;
    }
    if (typeof code === "string") {
      return code;
    }
  }
  return fallback;
}

export async function parseNiaErrorResponse(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as NiaErrorBody;
    return niaErrorMessageFromBody(body, response.statusText || "Request failed");
  } catch {
    return response.statusText || "Request failed";
  }
}

export type NiaSseKind = "text" | "thinking" | "tool_start" | "tool_end";

export type NiaSseEvent =
  | { kind: "text"; delta: string }
  | { kind: "thinking"; delta: string }
  | { kind: "tool_start"; name: string }
  | { kind: "tool_end"; name: string };

export type NiaSseHandlers = {
  onToken?: (delta: string) => void;
  onThinking?: (delta: string) => void;
  onTool?: (name: string, phase: "start" | "end") => void;
};

const TEXT_TYPES = new Set([
  "TEXT_MESSAGE_CONTENT",
  "TEXT_MESSAGE_CHUNK",
  "TEXT_DELTA",
]);

const THINKING_TYPES = new Set([
  "REASONING_MESSAGE_CONTENT",
  "REASONING_MESSAGE_CHUNK",
  "THINKING_TEXT_MESSAGE_CONTENT",
  "REASONING_DELTA",
  "THINKING_DELTA",
]);

const TOOL_START_TYPES = new Set(["TOOL_CALL_START", "TOOL_CALL_BEGIN"]);
const TOOL_END_TYPES = new Set(["TOOL_CALL_END", "TOOL_CALL_RESULT"]);

function normalizeType(value: unknown): string {
  return String(value ?? "")
    .trim()
    .toUpperCase()
    .replace(/-/g, "_");
}

function readString(...values: unknown[]): string | null {
  for (const value of values) {
    if (typeof value === "string" && value) {
      return value;
    }
  }
  return null;
}

function toolNameFromEvent(event: Record<string, unknown>): string {
  const nested =
    event.toolCall && typeof event.toolCall === "object"
      ? (event.toolCall as Record<string, unknown>)
      : event.tool_call && typeof event.tool_call === "object"
        ? (event.tool_call as Record<string, unknown>)
        : null;
  return (
    readString(
      event.toolCallName,
      event.tool_call_name,
      event.toolName,
      event.tool_name,
      event.name,
      nested?.name,
      nested?.toolCallName,
    ) ?? "tool"
  );
}

/** Parse one AG-UI SSE `data:` line. Ignores tool-arg deltas so they never enter the answer bubble. */
export function parseNiaSseLine(line: string): NiaSseEvent | null {
  const trimmed = line.trim();
  if (!trimmed.startsWith("data:")) {
    return null;
  }
  const payload = trimmed.slice(5).trim();
  if (!payload || payload === "[DONE]") {
    return null;
  }
  try {
    const event = JSON.parse(payload) as Record<string, unknown>;
    const type = normalizeType(event.type ?? event.event);
    const text = readString(event.delta, event.content, event.text);

    if (TOOL_START_TYPES.has(type)) {
      return { kind: "tool_start", name: toolNameFromEvent(event) };
    }
    if (TOOL_END_TYPES.has(type)) {
      return { kind: "tool_end", name: toolNameFromEvent(event) };
    }
    if (THINKING_TYPES.has(type) && text) {
      return { kind: "thinking", delta: text };
    }
    if (TEXT_TYPES.has(type) && text) {
      return { kind: "text", delta: text };
    }
  } catch {
    // ignore malformed SSE chunks
  }
  return null;
}

function normalizeHandlers(
  handlers?: ((delta: string) => void) | NiaSseHandlers,
): NiaSseHandlers {
  if (typeof handlers === "function") {
    return { onToken: handlers };
  }
  return handlers ?? {};
}

function dispatchSseEvent(event: NiaSseEvent, handlers: NiaSseHandlers): void {
  if (event.kind === "text") {
    handlers.onToken?.(event.delta);
    return;
  }
  if (event.kind === "thinking") {
    handlers.onThinking?.(event.delta);
    return;
  }
  handlers.onTool?.(event.name, event.kind === "tool_start" ? "start" : "end");
}

/** Consume AG-UI SSE to completion; optional callbacks for answer text, reasoning, and tools. */
export async function consumeNiaSse(
  response: Response,
  handlers?: ((delta: string) => void) | NiaSseHandlers,
): Promise<void> {
  const resolved = normalizeHandlers(handlers);

  if (!response.ok) {
    const message = await parseNiaErrorResponse(response);
    throw new ApiError(response.status, message);
  }

  const contentType = response.headers.get("content-type") ?? "";
  if (!contentType.includes("text/event-stream")) {
    await response.json().catch(() => undefined);
    return;
  }

  const reader = response.body?.getReader();
  if (!reader) {
    return;
  }

  const decoder = new TextDecoder();
  let buffer = "";

  for (;;) {
    const { done, value } = await reader.read();
    if (done) {
      break;
    }
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";
    for (const line of lines) {
      const event = parseNiaSseLine(line);
      if (event) {
        dispatchSseEvent(event, resolved);
      }
    }
  }

  if (buffer.trim()) {
    const event = parseNiaSseLine(buffer);
    if (event) {
      dispatchSseEvent(event, resolved);
    }
  }
}
