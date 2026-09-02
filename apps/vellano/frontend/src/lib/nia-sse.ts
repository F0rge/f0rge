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

function extractTextDelta(line: string): string | null {
  const trimmed = line.trim();
  if (!trimmed.startsWith("data:")) {
    return null;
  }
  const payload = trimmed.slice(5).trim();
  if (!payload || payload === "[DONE]") {
    return null;
  }
  try {
    const event = JSON.parse(payload) as {
      type?: string;
      delta?: string;
      content?: string;
      text?: string;
    };
    const type = event.type ?? "";
    if (
      type === "TEXT_MESSAGE_CONTENT" ||
      type === "text-delta" ||
      type === "TEXT_DELTA"
    ) {
      return event.delta ?? event.content ?? event.text ?? null;
    }
    if (typeof event.delta === "string") {
      return event.delta;
    }
  } catch {
    // ignore malformed SSE chunks
  }
  return null;
}

/** Consume AG-UI SSE to completion; optional token callback for live assistant text. */
export async function consumeNiaSse(
  response: Response,
  onToken?: (delta: string) => void,
): Promise<void> {
  if (!response.ok) {
    const message = await parseNiaErrorResponse(response);
    throw new ApiError(response.status, message);
  }

  const contentType = response.headers.get("content-type") ?? "";
  if (!contentType.includes("text/event-stream")) {
    await response.json();
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
      const delta = extractTextDelta(line);
      if (delta && onToken) {
        onToken(delta);
      }
    }
  }

  if (buffer.trim()) {
    const delta = extractTextDelta(buffer);
    if (delta && onToken) {
      onToken(delta);
    }
  }
}
