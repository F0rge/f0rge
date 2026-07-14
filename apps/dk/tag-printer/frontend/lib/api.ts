// Resolve the backend API base for the current environment.
// SSR/build uses the baked NEXT_PUBLIC_API_URL; in the browser we derive it from
// the current host so Cloudflare and LAN both work without a rebuild.
export function getApiBase(): string {
  const envUrl = process.env.NEXT_PUBLIC_API_URL;
  if (envUrl) return envUrl;

  if (typeof window === 'undefined') {
    return 'http://localhost:8002';
  }
  const host = window.location.hostname;
  if (host.endsWith('leo-figueiredo.com')) return 'https://tags-api.leo-figueiredo.com';
  return `http://${host}:8002`;
}
