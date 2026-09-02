export type NiaSseProxyAction = "run" | "resume";

export function niaApiBaseUrl(): string {
  return process.env.API_URL || "http://localhost:8003";
}

export function niaSseUpstreamUrl(threadId: string, action: NiaSseProxyAction): string {
  return `${niaApiBaseUrl()}/api/v1/nia/threads/${encodeURIComponent(threadId)}/${action}`;
}

export function niaSseResponseHeaders(upstreamContentType: string | null): Headers {
  const contentType = upstreamContentType ?? "text/event-stream";
  const headers = new Headers();
  headers.set("Content-Type", contentType);
  if (contentType.includes("text/event-stream")) {
    headers.set("Cache-Control", "no-cache, no-transform");
    headers.set("X-Accel-Buffering", "no");
    headers.set("Connection", "keep-alive");
  }
  return headers;
}

/** Same-origin POST that forwards the browser cookie and pipes SSE chunks. */
export async function proxyNiaSse(
  request: Request,
  threadId: string,
  action: NiaSseProxyAction,
): Promise<Response> {
  const headers = new Headers();
  const cookie = request.headers.get("cookie");
  if (cookie) {
    headers.set("cookie", cookie);
  }
  headers.set("content-type", request.headers.get("content-type") ?? "application/json");
  headers.set("accept", request.headers.get("accept") ?? "text/event-stream");

  const upstream = await fetch(niaSseUpstreamUrl(threadId, action), {
    method: "POST",
    headers,
    body: await request.arrayBuffer(),
    cache: "no-store",
  });

  const outHeaders = niaSseResponseHeaders(upstream.headers.get("content-type"));
  if (!upstream.body) {
    return new Response(await upstream.text(), {
      status: upstream.status,
      headers: outHeaders,
    });
  }

  const { readable, writable } = new TransformStream();
  void upstream.body.pipeTo(writable);
  return new Response(readable, { status: upstream.status, headers: outHeaders });
}
