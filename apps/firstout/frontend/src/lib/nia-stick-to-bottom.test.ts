import { describe, expect, it } from "vitest";

import {
  NIA_NEAR_BOTTOM_PX,
  isNearBottom,
  scrollElementToBottom,
} from "./nia-stick-to-bottom";

describe("isNearBottom", () => {
  it("is true when flush at the bottom", () => {
    expect(
      isNearBottom({ scrollTop: 400, scrollHeight: 500, clientHeight: 100 }),
    ).toBe(true);
  });

  it("is true within the default threshold", () => {
    expect(
      isNearBottom({
        scrollTop: 400 - NIA_NEAR_BOTTOM_PX,
        scrollHeight: 500,
        clientHeight: 100,
      }),
    ).toBe(true);
  });

  it("is false when the user has scrolled up past the threshold", () => {
    expect(
      isNearBottom({
        scrollTop: 400 - NIA_NEAR_BOTTOM_PX - 1,
        scrollHeight: 500,
        clientHeight: 100,
      }),
    ).toBe(false);
  });

  it("respects a custom threshold", () => {
    expect(
      isNearBottom({ scrollTop: 350, scrollHeight: 500, clientHeight: 100 }, 50),
    ).toBe(true);
    expect(
      isNearBottom({ scrollTop: 349, scrollHeight: 500, clientHeight: 100 }, 50),
    ).toBe(false);
  });
});

describe("scrollElementToBottom", () => {
  it("sets scrollTop to scrollHeight", () => {
    const el = { scrollTop: 0, scrollHeight: 900 } as HTMLElement;
    scrollElementToBottom(el);
    expect(el.scrollTop).toBe(900);
  });
});

/**
 * NiaConversation contract (nia-dock.tsx):
 * - onScroll sets stickToBottomRef via isNearBottom
 * - activeThreadId change force-pins to latest
 * - messages/streaming effect calls pinToBottom() only when stickToBottomRef is true
 * - handleSend must NOT set stickToBottomRef or force-pin (scrolled-up users stay put)
 */
describe("stick-to-bottom send contract", () => {
  it("documents that send must not flip stick when scrolled up", () => {
    // Pure helpers cannot assert React refs; guard the threshold used by onScroll
    // so a scrolled-up viewport stays non-sticky after send.
    const scrolledUp = {
      scrollTop: 0,
      scrollHeight: 2000,
      clientHeight: 400,
    };
    expect(isNearBottom(scrolledUp)).toBe(false);
  });
});
