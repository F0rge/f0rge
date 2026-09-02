import { describe, expect, it } from "vitest";

import { niaSseResponseHeaders, niaSseUpstreamUrl } from "./nia-sse-proxy";

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
