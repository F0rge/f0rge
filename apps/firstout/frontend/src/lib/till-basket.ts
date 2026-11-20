import { ApiError, type TillBasket, type TillBasketUpdate } from "./api";
import { basketContents, cartSnapshot, isUncertainHeldResponse, type BasketContents } from "./till-held-sales";

/** Equal keys mean the server already holds these contents. Linked-pick order is not significant. */
export function contentsKey(contents: BasketContents): string {
  return JSON.stringify({ ...contents, linked_pick_ids: Object.entries(contents.linked_pick_ids ?? {}).sort() });
}

/** The server basket moved on (stale version) or no longer matches what is being sold or held. */
export function isBasketConflict(error: unknown): boolean {
  return error instanceof ApiError && error.status === 409 && Boolean(
    error.detail && typeof error.detail === "object" && "code" in error.detail &&
    (error.detail.code === "basket_version_conflict" || error.detail.code === "basket_changed"),
  );
}

export type SavedBasket = { id: string; version: number };

type SaverOptions = {
  put: (id: string, body: TillBasketUpdate) => Promise<TillBasket>;
  /** The saver has stopped; reload the server basket. */
  onConflict: () => void;
  /** A save the server rejected; it is not retried until the contents change or flush() is called. */
  onError: (error: unknown) => void;
  retryDelay?: (attempt: number) => number;
};

/**
 * Keeps the server basket equal to the latest cart, one PUT at a time. An uncertain
 * failure resends the identical request (same operation_id and version), so a save the
 * server already applied is acknowledged rather than rejected as stale.
 */
export function createBasketSaver({
  put, onConflict, onError, retryDelay = (attempt) => Math.min(30_000, 1_000 * 2 ** attempt),
}: SaverOptions) {
  let basket: (SavedBasket & { key: string }) | null = null;
  let desired: BasketContents | null = null;
  let resend: { key: string; body: TillBasketUpdate } | null = null;
  let failedKey = "";
  let generation = 0;
  let attempts = 0;
  let busy = false;
  let current: Promise<void> = Promise.resolve();
  let timer: ReturnType<typeof setTimeout> | undefined;

  const dirty = () => basket !== null && (resend !== null || (desired !== null && contentsKey(desired) !== basket.key));

  async function run(): Promise<void> {
    busy = true;
    try {
      while (dirty() && basket) {
        const target = basket;
        const started = generation;
        const request = resend ?? {
          key: contentsKey(desired!),
          body: { ...desired!, version: target.version, operation_id: crypto.randomUUID() },
        };
        try {
          const saved = await put(target.id, request.body);
          if (started !== generation) continue;
          basket = { id: saved.id, version: saved.version, key: request.key };
          resend = null;
          attempts = 0;
        } catch (error) {
          if (started !== generation) continue;
          if (isBasketConflict(error)) {
            reset(null);
            onConflict();
          } else if (isUncertainHeldResponse(error)) {
            resend = request;
            clearTimeout(timer);
            timer = setTimeout(() => void start().catch(() => undefined), retryDelay(attempts++));
          } else {
            resend = null;
            failedKey = request.key;
            onError(error);
          }
          throw error;
        }
      }
    } finally {
      busy = false;
    }
  }

  function start(): Promise<void> {
    if (!busy) current = run();
    return current;
  }

  function reset(next: TillBasket | null) {
    generation += 1;
    clearTimeout(timer);
    resend = null;
    failedKey = "";
    attempts = 0;
    desired = null;
    basket = next && { id: next.id, version: next.version, key: contentsKey(basketContents(cartSnapshot(next))) };
  }

  return {
    reset,
    /** Background save of the latest cart. Failures are reported through the callbacks. */
    save(contents: BasketContents) {
      desired = contents;
      if (!resend && contentsKey(contents) !== failedKey) void start().catch(() => undefined);
    },
    /** Wait until the server holds the latest cart; throws if it cannot be saved now. */
    async flush(): Promise<SavedBasket> {
      clearTimeout(timer);
      failedKey = "";
      do await start(); while (dirty());
      if (!basket) throw new Error("The till basket is still loading. Try again in a moment.");
      return { id: basket.id, version: basket.version };
    },
    dispose() {
      clearTimeout(timer);
    },
  };
}
