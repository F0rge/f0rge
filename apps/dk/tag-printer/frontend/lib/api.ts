// Resolve the backend API base for the current environment.
// SSR/build uses the baked NEXT_PUBLIC_API_URL; in the browser we derive it from
// the current host so Cloudflare and LAN both work without a rebuild.
export function getApiBase(): string {
  if (typeof window === 'undefined') {
    return process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
  }
  const host = window.location.hostname;
  if (host.endsWith('leo-figueiredo.com')) return 'https://tags-api.leo-figueiredo.com';
  return `http://${host}:8000`;
}
