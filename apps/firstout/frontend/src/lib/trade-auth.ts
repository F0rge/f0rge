const INVITATION_KEY = "firstout:trade-invitation";
const INVITATION_TTL_MS = 15 * 60 * 1000;
type HandoffStorage = Pick<Storage, "getItem" | "setItem" | "removeItem">;

/** Only fixed local trade routes may be passed to Clerk; never an invitation secret. */
export function tradeReturnPath(value: string | null): string {
  if (!value?.startsWith("/") || value.startsWith("//")) return "/trade/catalogue";
  try {
    const url = new URL(value, "https://firstout.invalid");
    if (url.origin !== "https://firstout.invalid") return "/trade/catalogue";
    if (url.pathname === "/trade/accept-invitation") return url.pathname;
    if (url.pathname === "/trade/catalogue") {
      const access = url.searchParams.get("access");
      return access && /^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$/i.test(access) ? portalAccessUrl(access) : url.pathname;
    }
  } catch { /* Invalid destinations fall back to the account chooser. */ }
  return "/trade/catalogue";
}

export function tradeAuthUrl(mode: "login" | "sign-up", returnPath: string): string {
  return `/trade/${mode}?redirect_url=${encodeURIComponent(tradeReturnPath(returnPath))}`;
}

export function portalAccessUrl(accessId: string): string {
  return `/trade/catalogue?access=${encodeURIComponent(accessId)}`;
}

export function invitationTokenFromHash(hash: string): string | null {
  const token = new URLSearchParams(hash.replace(/^#/, "")).get("token");
  return token && token.length <= 4096 ? token : null;
}

export function rememberPortalInvitation(storage: HandoffStorage, token: string, now = Date.now()) {
  storage.setItem(INVITATION_KEY, JSON.stringify({ token, expiresAt: now + INVITATION_TTL_MS }));
}

export function readPortalInvitation(storage: HandoffStorage, now = Date.now()): string | null {
  const raw = storage.getItem(INVITATION_KEY);
  if (!raw) return null;
  try {
    const value: unknown = JSON.parse(raw);
    if (value && typeof value === "object" && "token" in value && "expiresAt" in value &&
      typeof value.token === "string" && value.token.length > 0 && value.token.length <= 4096 &&
      typeof value.expiresAt === "number" && value.expiresAt > now && value.expiresAt <= now + INVITATION_TTL_MS) return value.token;
  } catch { /* Discard expired or corrupt per-tab state. */ }
  clearPortalInvitation(storage);
  return null;
}

export function clearPortalInvitation(storage: HandoffStorage) {
  storage.removeItem(INVITATION_KEY);
}
