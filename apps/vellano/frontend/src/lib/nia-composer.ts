import type { NiaMessage } from "./api";

export type ComposerSendPlan =
  | { send: false }
  | { send: true; text: string; nextComposer: string };

/**
 * Decide what leaves the composer on send.
 *
 * The draft clears when the run starts (not when it ends), so anything typed
 * while Nia is streaming stays in the field instead of being truncated or
 * wiped later. A suggestion click (`override`) never touches the draft.
 */
export function planComposerSend(options: {
  composer: string;
  override?: string;
  streaming: boolean;
  blocked: boolean;
}): ComposerSendPlan {
  const { composer, override, streaming, blocked } = options;
  if (streaming || blocked) {
    return { send: false };
  }
  const text = (override ?? composer).trim();
  if (!text) {
    return { send: false };
  }
  return { send: true, text, nextComposer: override === undefined ? "" : composer };
}

export const OPTIMISTIC_USER_MESSAGE_ID = "nia-pending-user";

export function optimisticUserMessage(text: string, createdAt: string): NiaMessage {
  return {
    id: OPTIMISTIC_USER_MESSAGE_ID,
    role: "user",
    content: text,
    structured_payload: null,
    created_at: createdAt,
  };
}

/**
 * Show the prompt in the open thread while the run streams.
 *
 * Dropped once the persisted thread already ends with the same user text, so
 * the bubble never doubles up after the post-run `GET /threads/{id}`.
 */
export function withOptimisticUserMessage(
  messages: NiaMessage[],
  pending: NiaMessage | null,
): NiaMessage[] {
  if (!pending) {
    return messages;
  }
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    const message = messages[index];
    if (message.role !== "user") {
      continue;
    }
    return message.content === pending.content ? messages : [...messages, pending];
  }
  return [...messages, pending];
}
