import { describe, expect, it } from "vitest";
import { createPostHogBrowserProvider, POSTHOG_CAPTURE_URL, type PostHogCapturePayload } from "./posthog-browser";

describe("PostHog browser adapter", () => {
  it("posts only sanitized semantic events to the EU ingestion host", async () => {
    let requestUrl = "";
    let requestOptions: RequestInit | undefined;
    let payload: PostHogCapturePayload | undefined;
    const provider = createPostHogBrowserProvider({
      projectToken: "phc_test_fixture",
      createDistinctId: () => "anonymous-session-id",
      fetcher: async (input, init) => {
        requestUrl = String(input);
        requestOptions = init;
        payload = JSON.parse(String(init?.body)) as PostHogCapturePayload;
        return new Response("ok");
      },
    });

    provider.capture({
      name: "storefront_search_results_viewed",
      properties: { query_present: true, result_count: 2, availability: "all", price_filter_active: false, sort_order: "default" },
    });
    await Promise.resolve();

    expect(provider.isConfigured).toBe(true);
    expect(requestUrl).toBe(POSTHOG_CAPTURE_URL);
    expect(requestOptions).toMatchObject({ credentials: "omit", referrerPolicy: "no-referrer" });
    expect(payload).toEqual({
      api_key: "phc_test_fixture",
      event: "storefront_search_results_viewed",
      distinct_id: "anonymous-session-id",
      properties: { query_present: true, availability: "all", price_filter_active: false, sort_order: "default", result_count: 2 },
    });
  });

  it("does not send without a project token and ignores transport failures", () => {
    let requests = 0;
    const event = { name: "storefront_product_viewed", properties: { product_id: "prod_fixture" } } as const;
    const unconfigured = createPostHogBrowserProvider({ projectToken: "", fetcher: async () => { requests += 1; return new Response(); } });
    const failing = createPostHogBrowserProvider({ projectToken: "phc_test_fixture", fetcher: async () => { requests += 1; throw new Error("offline"); } });

    expect(() => unconfigured.capture(event)).not.toThrow();
    expect(() => failing.capture(event)).not.toThrow();
    expect(requests).toBe(1);
  });

  it("rotates the anonymous analytics id when a customer signs out", async () => {
    const ids = ["anonymous-before", "anonymous-after"];
    const sent: PostHogCapturePayload[] = [];
    const provider = createPostHogBrowserProvider({
      projectToken: "phc_test_fixture",
      createDistinctId: () => ids.shift() || "anonymous-next",
      fetcher: async (_input, init) => { sent.push(JSON.parse(String(init?.body)) as PostHogCapturePayload); return new Response("ok"); },
    });
    const event = { name: "storefront_product_viewed", properties: { product_id: "prod_fixture" } } as const;
    provider.capture(event);
    provider.resetIdentity();
    provider.capture(event);
    await Promise.resolve();

    expect(sent.map((payload) => payload.distinct_id)).toEqual(["anonymous-before", "anonymous-after"]);
  });

  it("aborts pending capture work and ignores events after consent is withdrawn", async () => {
    let signal: AbortSignal | undefined;
    let requests = 0;
    const provider = createPostHogBrowserProvider({
      projectToken: "phc_test_fixture",
      fetcher: (_input, init) => {
        signal = init?.signal as AbortSignal;
        requests += 1;
        return new Promise(() => undefined);
      },
    });
    const event = { name: "storefront_product_viewed", properties: { product_id: "prod_fixture" } } as const;

    provider.capture(event);
    provider.revoke();
    provider.capture(event);
    await Promise.resolve();

    expect(signal?.aborted).toBe(true);
    expect(requests).toBe(1);
  });
});
