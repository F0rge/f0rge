import { afterEach, describe, expect, it, vi } from "vitest";

import { niaSseResponseHeaders, niaSseUpstreamUrl, proxyNiaSse } from "./nia-sse-proxy";

describe("nia SSE proxy helpers", () => {
  it("keeps run and resume on the API host path", () => {
    expect(niaSseUpstreamUrl("thread-1", "run")).toContain(
      "/api/v1/nia/threads/thread-1/run",
    );
    expect(niaSseUpstreamUrl("thread-1", "resume")).toContain(
      "/api/v1/nia/threads/thread-1/resume",
    );
  });

  it("sets anti-buffering headers on event-stream responses", () => {
    const headers = niaSseResponseHeaders("text/event-stream");
    expect(headers.get("Content-Type")).toBe("text/event-stream");
    expect(headers.get("Cache-Control")).toBe("no-cache, no-transform");
    expect(headers.get("X-Accel-Buffering")).toBe("no");
    expect(headers.get("Connection")).toBe("keep-alive");
  });

  it("does not force SSE headers on JSON resume replies", () => {
    const headers = niaSseResponseHeaders("application/json");
    expect(headers.get("Content-Type")).toBe("application/json");
    expect(headers.get("X-Accel-Buffering")).toBeNull();
  });
});

describe("proxyNiaSse streaming", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("forwards each SSE chunk before the upstream run finishes", async () => {
    const encoder = new TextEncoder();
    const decoder = new TextDecoder();
    let push: (text: string) => void = () => undefined;
    let finish: () => void = () => undefined;
    const upstreamBody = new ReadableStream<Uint8Array>({
      start(controller) {
        push = (text) => controller.enqueue(encoder.encode(text));
        finish = () => controller.close();
      },
    });
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response(upstreamBody, {
            status: 200,
            headers: { "content-type": "text/event-stream" },
          }),
      ),
    );

    const request = new Request("http://localhost:3003/api/v1/nia/threads/t1/run", {
      method: "POST",
      headers: { "content-type": "application/json", cookie: "vellano_session=abc" },
      body: JSON.stringify({ message: "hi" }),
    });
    const response = await proxyNiaSse(request, "t1", "run");
    expect(response.headers.get("X-Accel-Buffering")).toBe("no");

    const reader = response.body?.getReader();
    expect(reader).toBeDefined();
    if (!reader) {
      return;
    }

    push('data: {"type":"TEXT_MESSAGE_CONTENT","delta":"Hel"}\n\n');
    const first = await reader.read();
    expect(decoder.decode(first.value)).toContain('"delta":"Hel"');

    push('data: {"type":"TEXT_MESSAGE_CONTENT","delta":"lo"}\n\n');
    const second = await reader.read();
    expect(decoder.decode(second.value)).toContain('"delta":"lo"');

    finish();
    expect((await reader.read()).done).toBe(true);
  });
});
