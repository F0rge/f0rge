export const PRODUCT_ATTENTION_IDLE_MS = 30_000;

export function isProductAttentionEligible(
  intersectionRatio: number,
  visibilityState: DocumentVisibilityState,
  hasFocus: boolean,
): boolean {
  return intersectionRatio >= 0.5 && visibilityState === "visible" && hasFocus;
}

/** Deterministic accumulator; callers decide whether the product region is measurable. */
export class ProductAttentionAccumulator {
  private eligible = false;
  private lastSampleAt: number | null = null;
  private lastInteractionAt: number | null = null;
  private finished = false;
  private accumulatedMilliseconds = 0;

  constructor(private readonly now: () => number = () => performance.now()) {}

  get activeMilliseconds(): number {
    return this.accumulatedMilliseconds;
  }

  setEligible(eligible: boolean): void {
    if (this.finished || this.eligible === eligible) return;
    if (!eligible) this.sample();
    this.eligible = eligible;
    const current = this.now();
    this.lastSampleAt = eligible ? current : null;
    if (eligible && this.lastInteractionAt === null) this.lastInteractionAt = current;
  }

  noteInteraction(): void {
    if (this.finished || !this.eligible) return;
    this.sample();
    const current = this.now();
    this.lastInteractionAt = current;
    this.lastSampleAt = current;
  }

  sample(): void {
    if (this.finished || !this.eligible) return;
    const current = this.now();
    if (this.lastSampleAt === null) {
      this.lastSampleAt = current;
      return;
    }
    const activeUntil = Math.min(current, (this.lastInteractionAt ?? current) + PRODUCT_ATTENTION_IDLE_MS);
    if (activeUntil > this.lastSampleAt) this.accumulatedMilliseconds += activeUntil - this.lastSampleAt;
    this.lastSampleAt = current;
  }

  finish(): number | null {
    if (this.finished) return null;
    this.sample();
    this.finished = true;
    this.eligible = false;
    return this.accumulatedMilliseconds > 0 ? Math.floor(this.accumulatedMilliseconds / 1000) : null;
  }
}
