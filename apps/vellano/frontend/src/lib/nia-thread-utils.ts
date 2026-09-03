import {
  isCanvasClearedPayload,
  isCanvasSpecPayload,
  type NiaMessage,
  type NiaThread,
} from "@/lib/api";
import { clearCanvasSpec, isCanvasCleared, writeCanvasSpec } from "@/lib/nia-canvas-store";
import { parseCanvasSpec, type CanvasSpec } from "@/lib/nia-canvas-types";

const STRUCTURED_CARD_KINDS = new Set([
  "needs_ok",
  "needs_fields",
  "opened_page",
  "canvas_spec",
  "canvas_cleared",
  "transfer_draft",
  "your_call",
  "overdue_invoices",
]);

export function messageHasStructuredCard(message: NiaMessage): boolean {
  const payload = message.structured_payload;
  if (!payload || typeof payload !== "object" || !("kind" in payload)) {
    return false;
  }
  return STRUCTURED_CARD_KINDS.has(String(payload.kind));
}

/** Dock prose is independent of structured cards (opened_page is optional extra). */
export function messageShowsDockProse(message: Pick<NiaMessage, "content">): boolean {
  return message.content.trim().length > 0;
}

export type LatestCanvasEvent =
  | { type: "spec"; spec: CanvasSpec; createdAt: string }
  | { type: "cleared"; createdAt: string };

export function latestCanvasEventFromMessages(
  messages: NiaMessage[],
): LatestCanvasEvent | null {
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    const message = messages[index];
    const payload = message?.structured_payload;
    if (!payload || typeof payload !== "object" || !("kind" in payload)) {
      continue;
    }
    if (isCanvasClearedPayload(payload)) {
      return { type: "cleared", createdAt: message.created_at };
    }
    if (isCanvasSpecPayload(payload)) {
      const spec = parseCanvasSpec(payload);
      if (spec) {
        return { type: "spec", spec, createdAt: message.created_at };
      }
    }
  }
  return null;
}

export function applyLatestCanvasEvent(event: LatestCanvasEvent): void {
  if (event.type === "cleared") {
    clearCanvasSpec();
    return;
  }
  writeCanvasSpec(event.spec);
}

export function syncCanvasSpecFromThread(thread: NiaThread): void {
  const event = latestCanvasEventFromMessages(thread.messages);
  if (!event) {
    return;
  }
  applyLatestCanvasEvent(event);
}

export function hydrateCanvasFromThreadMessages(
  threads: { messages: NiaMessage[] }[],
): boolean {
  if (isCanvasCleared()) {
    return false;
  }
  let newest: LatestCanvasEvent | null = null;
  for (const thread of threads) {
    const event = latestCanvasEventFromMessages(thread.messages);
    if (!event) {
      continue;
    }
    if (!newest || event.createdAt > newest.createdAt) {
      newest = event;
    }
  }
  if (!newest) {
    return false;
  }
  applyLatestCanvasEvent(newest);
  return newest.type === "spec";
}

export function formatRelativeThreadTime(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) {
    return "";
  }
  const diffMs = Date.now() - date.getTime();
  const diffMinutes = Math.floor(diffMs / 60_000);
  if (diffMinutes < 1) {
    return "Just now";
  }
  if (diffMinutes < 60) {
    return `${diffMinutes}m ago`;
  }
  const diffHours = Math.floor(diffMinutes / 60);
  if (diffHours < 24) {
    return `${diffHours}h ago`;
  }
  const diffDays = Math.floor(diffHours / 24);
  if (diffDays === 1) {
    return "Yesterday";
  }
  if (diffDays < 7) {
    return `${diffDays}d ago`;
  }
  return date.toLocaleDateString("en-ZA", { day: "numeric", month: "short" });
}
