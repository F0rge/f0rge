export function tenantHostFromHostname(hostname: string): string {
  const trimmed = hostname.trim().toLowerCase().replace(/\.$/, "");
  const [host] = trimmed.split(":");
  return host || trimmed;
}

export function tenantHostFromWindow(): string | null {
  if (typeof window === "undefined" || !window.location?.hostname) {
    return null;
  }
  return tenantHostFromHostname(window.location.hostname);
}

export function tenantHostFromRequest(request: Request): string | null {
  const explicit = request.headers.get("x-tenant-host");
  if (explicit) {
    return tenantHostFromHostname(explicit);
  }
  const host = request.headers.get("host");
  if (host) {
    return tenantHostFromHostname(host);
  }
  try {
    const hostname = new URL(request.url).hostname;
    return hostname ? tenantHostFromHostname(hostname) : null;
  } catch {
    return null;
  }
}

export function withTenantHeaders(init?: HeadersInit): Headers {
  const headers = new Headers(init);
  const host = tenantHostFromWindow();
  if (host && !headers.has("X-Tenant-Host")) {
    headers.set("X-Tenant-Host", host);
  }
  return headers;
}
