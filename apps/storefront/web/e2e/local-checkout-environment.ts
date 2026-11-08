type Environment = Record<string, string | undefined>;

/** Checkout QA writes carts, orders and reservations: refuse non-disposable targets. */
export function assertLocalCheckoutEnvironment(env: Environment): void {
  if (env.STOREFRONT_LOCAL_CHECKOUT_QA !== "true") {
    throw new Error("Live checkout QA requires STOREFRONT_LOCAL_CHECKOUT_QA=true");
  }
  const loopback = new Set(["localhost", "127.0.0.1", "::1", "[::1]"]);
  for (const [name, fallback, protocols] of [
    ["PLAYWRIGHT_BASE_URL", "http://127.0.0.1:3004", ["http:", "https:"]],
    ["MEDUSA_BACKEND_URL", "http://127.0.0.1:9000", ["http:", "https:"]],
    ["DATABASE_URL", "", ["postgres:", "postgresql:"]],
  ] as const) {
    let url: URL;
    try { url = new URL(env[name] || fallback); }
    catch { throw new Error(`Live checkout QA requires a valid local ${name}`); }
    if (!loopback.has(url.hostname) || !(protocols as readonly string[]).includes(url.protocol)) {
      throw new Error(`Live checkout QA refuses non-loopback ${name}`);
    }
    if (name === "DATABASE_URL" && !/^\/daskasas_checkout_[a-z0-9_]+$/.test(url.pathname)) {
      throw new Error("Live checkout QA requires a disposable daskasas_checkout_* database");
    }
    // pg connection-string query parameters can override the parsed host.
    if (name === "DATABASE_URL" && (url.search || url.hash)) {
      throw new Error("Live checkout QA refuses database URL query parameters or fragments");
    }
  }
}
