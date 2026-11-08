type TokenGetter = () => Promise<string | null>;
let getStaffToken: TokenGetter | null = null;
const listeners = new Set<() => void>();
export function subscribeStaffTransport(listener: () => void) {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}
export const staffTransportReady = () => getStaffToken !== null;
export const staffTransportServerReady = () => false;
/** Stores a token getter, never a token; each tab resolves its own active session. */
export function setStaffTokenGetter(getter: TokenGetter | null) {
  getStaffToken = getter;
  listeners.forEach((listener) => listener());
}
export async function staffFetch(
  path: string,
  options: RequestInit = {},
): Promise<Response> {
  const headers = new Headers(options.headers);
  // Customer authentication is deliberately separate from staff Organisations.
  if (!path.startsWith("/api/v1/portal") && getStaffToken) {
    const token = await getStaffToken();
    if (token) headers.set("Authorization", `Bearer ${token}`);
  }
  return fetch(path, { ...options, credentials: "include", headers });
}
