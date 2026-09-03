import {
  isCanvasClearedPayload,
  isCanvasSpecPayload,
  type NiaMessage,
  type NiaThread,
} from "@/lib/api";
import { canvasClearedAt, clearCanvasSpec, writeCanvasSpec } from "@/lib/nia-canvas-store";
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

const HAS_TIMEZONE = /(?:Z|[+-]\d{2}:?\d{2})$/i;

/** Thread timestamps are naive UTC from the API — read them as UTC, not local. */
export function canvasEventInstant(value: string | null | undefined): number | null {
  if (!value) {
    return null;
  }
  const parsed = Date.parse(HAS_TIMEZONE.test(value) ? value : `${value}Z`);
  return Number.isNaN(parsed) ? null : parsed;
}

function absoluteIso(value: string): string | undefined {
  const instant = canvasEventInstant(value);
  return instant === null ? undefined : new Date(instant).toISOString();
}

export function applyLatestCanvasEvent(event: LatestCanvasEvent): void {
  if (event.type === "cleared") {
    clearCanvasSpec(absoluteIso(event.createdAt));
    return;
  }
  writeCanvasSpec(event.spec);
}

/** A local clear only blocks hydrate for canvas events it is newer than.
 *
 * A chart tool followed by a write tool in one run persists the chart as its
 * own thread message, so `/canvas` has to hydrate it even when this browser
 * cleared the canvas earlier — otherwise the sentinel hides every later chart.
 */
function eventOutranksLocalClear(createdAt: string): boolean {
  const clearedAt = canvasClearedAt();
  if (clearedAt === null) {
    return true;
  }
  const event = canvasEventInstant(createdAt);
  const cleared = canvasEventInstant(clearedAt);
  if (event === null || cleared === null) {
    return false;
  }
  return event > cleared;
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
  let newest: LatestCanvasEvent | null = null;
  let newestInstant = Number.NEGATIVE_INFINITY;
  for (const thread of threads) {
    const event = latestCanvasEventFromMessages(thread.messages);
    if (!event) {
      continue;
    }
    const instant = canvasEventInstant(event.createdAt) ?? Number.NEGATIVE_INFINITY;
    if (!newest || instant > newestInstant) {
      newest = event;
      newestInstant = instant;
    }
  }
  if (!newest || !eventOutranksLocalClear(newest.createdAt)) {
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
