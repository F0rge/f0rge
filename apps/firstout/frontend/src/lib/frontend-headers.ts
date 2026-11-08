import { createHmac } from "node:crypto";
import { frontendHost } from "./tenant-host";

export function frontendHeaders(
  original: Headers,
  allowLocal = false,
  secret?: string,
): Headers | null {
  const host = frontendHost(original.get("host"), allowLocal);
  if (!host) return null;
  const headers = new Headers(original);
  headers.delete("x-forwarded-host");
  headers.delete("forwarded");
  headers.delete("x-firstout-proxy-secret");
  headers.delete("x-firstout-proxy-signature");
  headers.set("x-firstout-frontend-host", host);
  if (secret)
    headers.set(
      "x-firstout-proxy-signature",
      createHmac("sha256", secret).update(host).digest("hex"),
    );
  return headers;
}
