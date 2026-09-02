import { proxyNiaSse } from "@/lib/nia-sse-proxy";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type RouteContext = { params: Promise<{ threadId: string }> };

/** Same-origin SSE/JSON pipe for HITL resume — cookie stays on the frontend host. */
export async function POST(request: Request, context: RouteContext): Promise<Response> {
  const { threadId } = await context.params;
  return proxyNiaSse(request, threadId, "resume");
}
