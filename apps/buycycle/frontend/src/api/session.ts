/** One verified browser identity epoch. Old work cannot publish into a new epoch. */
export class IdentitySession {
  readonly epoch = crypto.randomUUID();
  readonly controller = new AbortController();
  constructor(readonly subject: string) {}
  get active() {
    return !this.controller.signal.aborted;
  }
  invalidate() {
    this.controller.abort();
  }
  assertActive() {
    if (!this.active) throw new IdentityChanged();
  }
  request(signal?: AbortSignal) {
    this.assertActive();
    return {
      headers: { "X-Buycycle-Expected-Identity": this.subject },
      signal: signal
        ? AbortSignal.any([signal, this.controller.signal])
        : this.controller.signal,
    };
  }
}
export class IdentityChanged extends Error {
  constructor() {
    super("The signed-in identity changed. This response was discarded.");
    this.name = "IdentityChanged";
  }
}
