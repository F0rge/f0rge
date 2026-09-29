import {
  availableCapacity,
  consumeCapacity,
  mergeCapacityState,
  readCapacityState,
  releaseCapacityHold,
  releaseExpiredCapacityHolds,
  reserveCapacity,
  type MadeToOrderOffer,
} from "./made-to-order-capacity";

const acceptedAt = new Date("2026-09-28T12:00:00.000Z");
const offer: MadeToOrderOffer = {
  id: "bcd2f5d4-237b-43fb-a152-bef10a6a3eaa",
  capacity: 1,
  min_lead_time_days: 28,
  max_lead_time_days: 42,
  expires_at: "2026-10-15T12:00:00.000Z",
};

function initialState() {
  return mergeCapacityState(null, offer, "2026-09-28T11:00:00.000000Z");
}

test("serializes concurrent last-capacity attempts under one distributed lock", async () => {
  let state = initialState();
  let tail = Promise.resolve();
  const attempt = (cartId: string) => {
    const result = tail.then(() => {
      const reserved = reserveCapacity(
        state, offer.id, cartId, `line-${cartId}`, 1,
        "2026-09-28T12:20:00.000Z", acceptedAt,
      );
      state = reserved;
      return reserved;
    });
    tail = result.then(() => undefined, () => undefined);
    return result;
  };

  const outcomes = await Promise.allSettled([attempt("cart-a"), attempt("cart-b")]);
  expect(outcomes.filter((outcome) => outcome.status === "fulfilled")).toHaveLength(1);
  expect(outcomes.filter((outcome) => outcome.status === "rejected")).toHaveLength(1);
  expect(availableCapacity(state.allocations[offer.id], acceptedAt.getTime())).toBe(0);
});

test("declines keep a live hold for retry; cancel and expiry release capacity once", () => {
  const held = reserveCapacity(
    initialState(), offer.id, "cart-a", "line-a", 1,
    "2026-09-28T12:20:00.000Z", acceptedAt,
  );
  // A declined/pending provider event deliberately leaves the capacity hold untouched.
  expect(availableCapacity(held.allocations[offer.id], acceptedAt.getTime())).toBe(0);
  const cancelled = releaseCapacityHold(held, "cart-a", "line-a");
  expect(cancelled.released).toBe(true);
  expect(releaseCapacityHold(cancelled.state, "cart-a", "line-a").released).toBe(false);
  expect(availableCapacity(cancelled.state.allocations[offer.id], acceptedAt.getTime())).toBe(1);

  const expiredHold = reserveCapacity(
    initialState(), offer.id, "cart-b", "line-b", 1,
    "2026-09-28T12:20:00.000Z", acceptedAt,
  );
  const expired = releaseExpiredCapacityHolds(expiredHold, Date.parse("2026-09-28T12:20:00.000Z"));
  expect(expired.released).toBe(1);
  expect(releaseExpiredCapacityHolds(expired.state, Date.parse("2026-09-28T12:21:00.000Z")).released).toBe(0);
  expect(availableCapacity(expired.state.allocations[offer.id], Date.parse("2026-09-28T12:21:00.000Z"))).toBe(1);
});

test("success consumes once and replayed stale catalogue sync cannot restore the paid unit", () => {
  const held = reserveCapacity(
    initialState(), offer.id, "cart-a", "line-a", 1,
    "2026-09-28T12:20:00.000Z", acceptedAt,
  );
  const committed = consumeCapacity(
    held, offer.id, "cart-a", "line-a", "storefront:order-a:item-a", 1,
    Date.parse("2026-09-28T12:01:00.000Z"),
  );
  expect(consumeCapacity(
    committed, offer.id, "cart-a", "line-a", "storefront:order-a:item-a", 1,
    Date.parse("2026-09-28T12:02:00.000Z"),
  )).toBe(committed);
  expect(availableCapacity(committed.allocations[offer.id], acceptedAt.getTime())).toBe(0);

  const replayed = mergeCapacityState({
    source_revision: "2026-09-28T12:00:00.000000Z",
    storefront_made_to_order_capacity: committed,
  }, { ...offer, capacity: 1 }, "2026-09-28T11:59:59.000000Z");
  expect(replayed.allocations[offer.id].committed).toEqual(committed.allocations[offer.id].committed);
  expect(availableCapacity(replayed.allocations[offer.id], acceptedAt.getTime())).toBe(0);
});

test("an offer expiry blocks consumption even when the separate hold TTL still has time", () => {
  const held = reserveCapacity(
    initialState(), offer.id, "cart-expiry", "line-expiry", 1,
    "2026-11-01T12:00:00.000Z", acceptedAt,
  );
  expect(() => consumeCapacity(
    held, offer.id, "cart-expiry", "line-expiry", "storefront:order-expiry:item-expiry", 1,
    Date.parse(offer.expires_at),
  )).toThrow("made_to_order_capacity_hold_expired");
});

test("parses persisted state fail-closed instead of treating corruption as free capacity", () => {
  expect(() => readCapacityState({ storefront_made_to_order_capacity: { version: 2, allocations: {} } })).toThrow();
});
