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

export type NiaSseKind = "text" | "thinking" | "tool_start" | "tool_end" | "milestone";

export type NiaSseEvent =
  | { kind: "text"; delta: string }
  | { kind: "thinking"; delta: string }
  | { kind: "tool_start"; name: string }
  | { kind: "tool_end"; name: string }
  | { kind: "milestone"; label: string };

export type NiaSseHandlers = {
  onToken?: (delta: string) => void;
  onThinking?: (delta: string) => void;
  onTool?: (name: string, phase: "start" | "end") => void;
  onMilestone?: (label: string) => void;
};

const TEXT_TYPES = new Set([
  "TEXT_MESSAGE_CONTENT",
  "TEXT_MESSAGE_CHUNK",
  "TEXT_DELTA",
  "TEXT_MESSAGE_DELTA",
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
const CUSTOM_TYPES = new Set(["CUSTOM"]);

const LIFECYCLE_TYPES = new Set([
  "TEXT_MESSAGE_START",
  "TEXT_MESSAGE_END",
  "THINKING_START",
  "THINKING_END",
  "THINKING_TEXT_MESSAGE_START",
  "THINKING_TEXT_MESSAGE_END",
  "REASONING_START",
  "REASONING_END",
  "REASONING_MESSAGE_START",
  "REASONING_MESSAGE_END",
  "TOOL_CALL_ARGS",
  "RUN_STARTED",
  "RUN_FINISHED",
  "RUN_ERROR",
  "STEP_STARTED",
  "STEP_FINISHED",
]);

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

function isMilestoneName(value: unknown): boolean {
  const raw = String(value ?? "")
    .trim()
    .toLowerCase();
  return raw === "milestone" || raw === "nia.milestone" || raw === "nia_milestone";
}

/** Label from an AG-UI CustomEvent `value` (`{label}` / `{step}` or a string). */
export function milestoneLabelFromValue(value: unknown): string | null {
  if (typeof value === "string" && value.trim()) {
    return value.trim();
  }
  const record = asRecord(value);
  if (!record) {
    return null;
  }
  for (const key of ["label", "step", "text", "message"] as const) {
    const candidate = record[key];
    if (typeof candidate === "string" && candidate.trim()) {
      return candidate.trim();
    }
  }
  return null;
}

/** `TextMessageContent` / `text-delta` / `TEXT_MESSAGE_CONTENT` → `TEXT_MESSAGE_CONTENT`. */
export function normalizeNiaSseType(value: unknown): string {
  const raw = String(value ?? "").trim();
  if (!raw) {
    return "";
  }
  return raw
    .replace(/([a-z0-9])([A-Z])/g, "$1_$2")
    .replace(/[-\s]+/g, "_")
    .replace(/__+/g, "_")
    .toUpperCase();
}

function readType(event: Record<string, unknown>): string {
  const nestedEvent = asRecord(event.event);
  const nestedData = asRecord(event.data);
  return normalizeNiaSseType(
    event.type ?? nestedEvent?.type ?? nestedData?.type ?? event.event,
  );
}

function readString(...values: unknown[]): string | null {
  for (const value of values) {
    if (typeof value === "string" && value) {
      return value;
    }
  }
  return null;
}

function readDelta(event: Record<string, unknown>): string | null {
  const nestedEvent = asRecord(event.event);
  const nestedData = asRecord(event.data);
  return readString(
    event.delta,
    event.content,
    event.text,
    nestedEvent?.delta,
    nestedEvent?.content,
    nestedEvent?.text,
    nestedData?.delta,
    nestedData?.content,
    nestedData?.text,
  );
}

function toolNameFromEvent(event: Record<string, unknown>): string {
  const nested =
    asRecord(event.toolCall) ??
    asRecord(event.tool_call) ??
    asRecord(event.event) ??
    asRecord(event.data);
  return (
    readString(
      event.toolCallName,
      event.tool_call_name,
      event.toolName,
      event.tool_name,
      event.name,
      nested?.name,
      nested?.toolCallName,
      nested?.tool_call_name,
    ) ?? "tool"
  );
}

function ssePayload(line: string): string | null {
  const trimmed = line.trim();
  if (!trimmed.startsWith("data:")) {
    return null;
  }
  const payload = trimmed.slice(5).trim();
  if (!payload || payload === "[DONE]") {
    return null;
  }
  return payload;
}

export function peekNiaSseType(line: string): string | null {
  const payload = ssePayload(line);
  if (!payload) {
    return null;
  }
  try {
    const event = asRecord(JSON.parse(payload));
    if (!event) {
      return null;
    }
    const type = readType(event);
    return type || null;
  } catch {
    return null;
  }
}

function logUnknownNiaSseType(type: string): void {
  if (process.env.NODE_ENV === "production") {
    return;
  }
  if (TEXT_TYPES.has(type) || THINKING_TYPES.has(type)) {
    return;
  }
  if (TOOL_START_TYPES.has(type) || TOOL_END_TYPES.has(type) || LIFECYCLE_TYPES.has(type)) {
    return;
  }
  if (CUSTOM_TYPES.has(type)) {
    return;
  }
  console.info("[nia-sse] unknown event type", type);
}

/** Parse one AG-UI SSE `data:` line. Ignores tool-arg deltas so they never enter the answer bubble. */
export function parseNiaSseLine(line: string): NiaSseEvent | null {
  const payload = ssePayload(line);
  if (!payload) {
    return null;
  }
  try {
    const event = asRecord(JSON.parse(payload));
    if (!event) {
      return null;
    }
    const type = readType(event);
    const text = readDelta(event);

    if (TOOL_START_TYPES.has(type)) {
      return { kind: "tool_start", name: toolNameFromEvent(event) };
    }
    if (TOOL_END_TYPES.has(type)) {
      return { kind: "tool_end", name: toolNameFromEvent(event) };
    }
    if (CUSTOM_TYPES.has(type)) {
      const nestedEvent = asRecord(event.event);
      const nestedData = asRecord(event.data);
      const name = readString(event.name, nestedEvent?.name, nestedData?.name);
      if (isMilestoneName(name)) {
        const label = milestoneLabelFromValue(
          event.value ?? nestedEvent?.value ?? nestedData?.value,
        );
        if (label) {
          return { kind: "milestone", label };
        }
      }
      return null;
    }
    if (THINKING_TYPES.has(type) && text) {
      return { kind: "thinking", delta: text };
    }
    if (TEXT_TYPES.has(type) && text) {
      return { kind: "text", delta: text };
    }
    if (type) {
      logUnknownNiaSseType(type);
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
  if (event.kind === "milestone") {
    handlers.onMilestone?.(event.label);
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
