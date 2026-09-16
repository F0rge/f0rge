export async function fetchSlugAvailability(
  slug: string,
): Promise<{ available: boolean; reason?: string }> {
  const res = await fetch(`/api/v1/platform/slugs/${encodeURIComponent(slug)}/availability`);
  if (!res.ok) {
    return { available: false, reason: "invalid" };
  }
  return (await res.json()) as { available: boolean; reason?: string };
}

export async function createSignup(body: Record<string, unknown>): Promise<Response> {
  return fetch("/api/v1/platform/signups", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
}

export async function resendSignup(signupId: string): Promise<Response> {
  return fetch(`/api/v1/platform/signups/${encodeURIComponent(signupId)}/resend`, {
    method: "POST",
  });
}

export async function verifySignup(token: string): Promise<Response> {
  return fetch("/api/v1/platform/signups/verify", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ token }),
  });
}

export async function signupStatus(signupId: string): Promise<Response> {
  return fetch(`/api/v1/platform/signups/${encodeURIComponent(signupId)}/status`);
}
