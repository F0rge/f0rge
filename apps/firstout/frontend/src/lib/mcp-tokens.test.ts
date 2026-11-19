import { afterEach, describe, expect, it, vi } from "vitest";
import { generateMcpToken, listMcpTokens, revokeMcpToken, rotateMcpToken } from "./mcp-tokens";

afterEach(() => vi.unstubAllGlobals());

describe("personal MCP token requests", () => {
  it("reads the active staff directory without browser caching and submits the requested expiry", async () => {
    const fetch = vi.fn(async () => Response.json({}));
    vi.stubGlobal("fetch", fetch);

    await listMcpTokens();
    await generateMcpToken("Desk", 90);

    expect(fetch).toHaveBeenNthCalledWith(1, "/api/v1/mcp-tokens", expect.objectContaining({ cache: "no-store" }));
    expect(fetch).toHaveBeenNthCalledWith(2, "/api/v1/mcp-tokens", expect.objectContaining({
      method: "POST",
      body: JSON.stringify({ name: "Desk", expires_in_days: 90 }),
    }));
  });

  it("uses the reviewed rotation version and revokes the specific token", async () => {
    const fetch = vi.fn()
      .mockResolvedValueOnce(Response.json({ token: { id: "id/1", version: 8 }, secret: "sample-secret" }))
      .mockResolvedValueOnce(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetch);

    await expect(rotateMcpToken({ id: "id/1", version: 7 })).resolves.toMatchObject({ token: { version: 8 } });
    await expect(revokeMcpToken("id/1")).resolves.toBeUndefined();

    expect(fetch).toHaveBeenNthCalledWith(1, "/api/v1/mcp-tokens/id%2F1/rotate", expect.objectContaining({
      method: "POST", body: JSON.stringify({ version: 7 }),
    }));
    expect(fetch).toHaveBeenNthCalledWith(2, "/api/v1/mcp-tokens/id%2F1", expect.objectContaining({ method: "DELETE" }));
  });
});
