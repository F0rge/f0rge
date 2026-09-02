import { isCanvasSpecPayload, type NiaMessage, type NiaThread } from "@/lib/api";
import { writeCanvasSpec } from "@/lib/nia-canvas-store";

const STRUCTURED_CARD_KINDS = new Set([
  "needs_ok",
  "opened_page",
  "canvas_spec",
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

export function syncCanvasSpecFromThread(thread: NiaThread): void {
  for (let index = thread.messages.length - 1; index >= 0; index -= 1) {
    const payload = thread.messages[index]?.structured_payload;
    if (payload && isCanvasSpecPayload(payload)) {
      writeCanvasSpec(payload);
      return;
    }
  }
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
