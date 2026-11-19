import { apiFetch } from "./api";

export const MCP_TOKEN_EXPIRY_DAYS = [7, 30, 90] as const;
export const MCP_TOKEN_NAME_LIMIT = 80;
export type McpTokenExpiryDays = typeof MCP_TOKEN_EXPIRY_DAYS[number];

export type McpToken = {
  id: string;
  name: string;
  suffix: string;
  expires_at: string;
  last_used_at: string | null;
  status: "active" | "revoked" | "expired";
  version: number;
};

export type McpTokenActivity = {
  id: string;
  action: "generated" | "rotated" | "revoked" | "catalogue_searched";
  source: "firstout" | "mcp";
  token_name: string;
  result: "success" | "denied";
  occurred_at: string;
};

export type McpTokenDirectory = {
  endpoint: string;
  tokens: McpToken[];
  activity: McpTokenActivity[];
};

type IssuedToken = {
  token: McpToken;
  secret: string;
};

export const listMcpTokens = () => apiFetch<McpTokenDirectory>("/mcp-tokens", { cache: "no-store" });

export const generateMcpToken = (name: string, expiresInDays: McpTokenExpiryDays) =>
  apiFetch<IssuedToken>("/mcp-tokens", {
    method: "POST",
    body: JSON.stringify({ name, expires_in_days: expiresInDays }),
  });

export const rotateMcpToken = ({ id, version }: Pick<McpToken, "id" | "version">) =>
  apiFetch<IssuedToken>("/mcp-tokens/" + encodeURIComponent(id) + "/rotate", {
    method: "POST",
    body: JSON.stringify({ version }),
  });

export const revokeMcpToken = (id: string) =>
  apiFetch<void>("/mcp-tokens/" + encodeURIComponent(id), { method: "DELETE" });
