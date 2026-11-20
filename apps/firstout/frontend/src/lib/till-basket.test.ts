import { describe, expect, it, vi } from "vitest";

import { ApiError, type TillBasket, type TillBasketUpdate } from "./api";
import { contentsKey, createBasketSaver, isBasketConflict } from "./till-basket";
import { basketContents, cartSnapshot } from "./till-held-sales";

const server: TillBasket = {
  id: "basket", location_id: "showroom", customer_id: "customer", note: null, pick_id: "pick-b",
  linked_pick_ids: { "kit-b": "pick-b", "kit-a": "pick-a" },
  lines: [
    { sku_id: "kit-a", qty: 1, discount_percent: "0" },
    { sku_id: "kit-b", qty: 2, discount_percent: "12.5000" },
  ],
  version: 4, updated_at: "2026-11-20T08:00:00Z",
};

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (error: unknown) => void;
  const promise = new Promise<T>((ok, fail) => { resolve = ok; reject = fail; });
  return { promise, resolve, reject };
}

function harness() {
  const calls: { id: string; body: TillBasketUpdate; reply: ReturnType<typeof deferred<TillBasket>> }[] = [];
  const onConflict = vi.fn();
  const onError = vi.fn();
  const saver = createBasketSaver({
    put: (id, body) => {
      const reply = deferred<TillBasket>();
      calls.push({ id, body, reply });
      return reply.promise;
    },
    onConflict, onError, retryDelay: () => 60_000,
  });
  saver.reset(server);
  const accept = (index: number) => {
    const { body } = calls[index];
    calls[index].reply.resolve({ ...server, version: body.version + 1 });
  };
  return { saver, calls, onConflict, onError, accept };
}

const cart = (qty: number) => basketContents({ ...cartSnapshot(server), lines: [{ skuId: "kit-a", qty, discountPercent: 0 }] });
const tick = () => new Promise((resolve) => setTimeout(resolve, 0));

describe("till basket mapping", () => {
  it("treats the server basket and the same cart as already saved", () => {
    const snapshot = cartSnapshot(server);
    expect(snapshot.lines[1]).toEqual({ skuId: "kit-b", qty: 2, discountPercent: 12.5 });
    const reordered = { ...snapshot, linkedPickIds: { "kit-a": "pick-a", "kit-b": "pick-b" } };
    expect(contentsKey(basketContents(reordered))).toBe(contentsKey(basketContents(snapshot)));
    expect(basketContents(snapshot)).toEqual({
      customer_id: "customer", pick_id: "pick-b",
      linked_pick_ids: { "kit-b": "pick-b", "kit-a": "pick-a" },
      lines: [{ sku_id: "kit-a", qty: 1 }, { sku_id: "kit-b", qty: 2, discount_percent: 12.5 }],
    });
  });

  it("recognises only basket conflicts", () => {
    expect(isBasketConflict(new ApiError(409, "Changed", { code: "basket_version_conflict", basket: server }))).toBe(true);
    expect(isBasketConflict(new ApiError(409, "Changed", { code: "basket_changed", basket: server }))).toBe(true);
    expect(isBasketConflict(new ApiError(409, "Reserved", { code: "stock_reserved", basket: server }))).toBe(true);
    expect(isBasketConflict(new ApiError(409, "Expired", { code: "basket_expired", basket: server }))).toBe(true);
    expect(isBasketConflict(new ApiError(409, "Price", { code: "till_price_conflict" }))).toBe(false);
    expect(isBasketConflict(new ApiError(0, "Offline"))).toBe(false);
  });
});

describe("till basket saver", () => {
  it("does not save a cart the server already holds", async () => {
    const { saver, calls } = harness();
    saver.save(basketContents(cartSnapshot(server)));
    await expect(saver.flush()).resolves.toEqual({ id: "basket", version: 4 });
    expect(calls).toHaveLength(0);
  });

  it("keeps one save in flight and sends the latest cart with the returned version", async () => {
    const { saver, calls, accept } = harness();
    saver.save(cart(1));
    saver.save(cart(2));
    saver.save(cart(3));
    expect(calls).toHaveLength(1);
    expect(calls[0].body).toMatchObject({ version: 4, lines: [{ sku_id: "kit-a", qty: 1 }] });
    accept(0);
    await tick();
    expect(calls).toHaveLength(2);
    expect(calls[1].body).toMatchObject({ version: 5, lines: [{ sku_id: "kit-a", qty: 3 }] });
    const flushed = saver.flush();
    accept(1);
    await expect(flushed).resolves.toEqual({ id: "basket", version: 6 });
  });

  it("resends an uncertain save unchanged so a retry is safe", async () => {
    const { saver, calls, accept, onError } = harness();
    saver.save(cart(1));
    calls[0].reply.reject(new ApiError(0, "PUT /till/basket failed"));
    await tick();
    saver.save(cart(2));
    expect(calls).toHaveLength(1);
    const flushed = saver.flush();
    expect(calls[1].body).toEqual(calls[0].body);
    accept(1);
    await tick();
    expect(calls[2].body).toMatchObject({ version: 5, lines: [{ qty: 2 }] });
    expect(calls[2].body.operation_id).not.toBe(calls[0].body.operation_id);
    accept(2);
    await expect(flushed).resolves.toEqual({ id: "basket", version: 6 });
    expect(onError).not.toHaveBeenCalled();
  });

  it("stops and asks for a reload when the basket changed elsewhere", async () => {
    const { saver, calls, onConflict } = harness();
    saver.save(cart(1));
    const flushed = saver.flush();
    calls[0].reply.reject(new ApiError(409, "The basket changed.", { code: "basket_version_conflict", basket: server }));
    await expect(flushed).rejects.toThrow("The basket changed.");
    expect(onConflict).toHaveBeenCalledOnce();
    saver.save(cart(2));
    await expect(saver.flush()).rejects.toThrow("still loading");
    expect(calls).toHaveLength(1);
  });

  it("reports a rejected save once and tries again only when asked", async () => {
    const { saver, calls, onError } = harness();
    saver.save(cart(1));
    calls[0].reply.reject(new ApiError(422, "Restore SKU KIT-A before adding it to new business"));
    await tick();
    expect(onError).toHaveBeenCalledOnce();
    saver.save(cart(1));
    expect(calls).toHaveLength(1);
    const flushed = saver.flush();
    calls[1].reply.reject(new ApiError(422, "Restore SKU KIT-A before adding it to new business"));
    await expect(flushed).rejects.toThrow("Restore SKU");
  });
});
