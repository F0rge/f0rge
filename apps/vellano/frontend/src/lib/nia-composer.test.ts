import { describe, expect, it } from "vitest";

import type { NiaMessage } from "./api";
import {
  OPTIMISTIC_USER_MESSAGE_ID,
  optimisticUserMessage,
  planComposerSend,
  withOptimisticUserMessage,
} from "./nia-composer";

const SENTENCE = "also open the transfer page";

function userMessage(content: string, id = "m1"): NiaMessage {
  return {
    id,
    role: "user",
    content,
    structured_payload: null,
    created_at: "2026-09-03T10:00:00Z",
  };
}

describe("planComposerSend", () => {
  it("sends exactly what was typed, spaces included", () => {
    expect(
      planComposerSend({ composer: SENTENCE, streaming: false, blocked: false }),
    ).toEqual({ send: true, text: SENTENCE, nextComposer: "" });
  });

  it("keeps inner spacing and punctuation untouched", () => {
    const typed = "tell me  something about the fabric";
    const plan = planComposerSend({ composer: typed, streaming: false, blocked: false });
    expect(plan).toMatchObject({ send: true, text: typed });
  });

  it("clears the draft at send time so a later run end cannot wipe new typing", () => {
    const plan = planComposerSend({
      composer: `  ${SENTENCE}  `,
      streaming: false,
      blocked: false,
    });
    expect(plan).toEqual({ send: true, text: SENTENCE, nextComposer: "" });
  });

  it("does not send while a run is streaming and keeps the draft", () => {
    expect(
      planComposerSend({ composer: "navigate to transfers", streaming: true, blocked: false }),
    ).toEqual({ send: false });
  });

  it("does not send when the monthly allowance is used", () => {
    expect(
      planComposerSend({ composer: "hi", streaming: false, blocked: true }),
    ).toEqual({ send: false });
  });

  it("does not send whitespace", () => {
    expect(
      planComposerSend({ composer: "   \n ", streaming: false, blocked: false }),
    ).toEqual({ send: false });
  });

  it("a suggestion click leaves a half-typed draft alone", () => {
    expect(
      planComposerSend({
        composer: "half typed thought",
        override: "Create a SKU",
        streaming: false,
        blocked: false,
      }),
    ).toEqual({ send: true, text: "Create a SKU", nextComposer: "half typed thought" });
  });
});

describe("withOptimisticUserMessage", () => {
  it("shows the prompt in the open thread while the run streams", () => {
    const pending = optimisticUserMessage(SENTENCE, "2026-09-03T10:00:01Z");
    const merged = withOptimisticUserMessage([], pending);
    expect(merged).toHaveLength(1);
    expect(merged[0].id).toBe(OPTIMISTIC_USER_MESSAGE_ID);
    expect(merged[0].content).toBe(SENTENCE);
  });

  it("appends after earlier turns", () => {
    const pending = optimisticUserMessage(SENTENCE, "2026-09-03T10:00:01Z");
    const merged = withOptimisticUserMessage([userMessage("hi")], pending);
    expect(merged.map((message) => message.content)).toEqual(["hi", SENTENCE]);
  });

  it("does not double the bubble once the thread reload contains it", () => {
    const pending = optimisticUserMessage(SENTENCE, "2026-09-03T10:00:01Z");
    const merged = withOptimisticUserMessage([userMessage(SENTENCE, "persisted")], pending);
    expect(merged).toHaveLength(1);
    expect(merged[0].id).toBe("persisted");
  });

  it("is a no-op with nothing pending", () => {
    const messages = [userMessage("hi")];
    expect(withOptimisticUserMessage(messages, null)).toBe(messages);
  });
});
