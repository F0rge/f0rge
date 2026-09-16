export const SLUG_PATTERN = /^[a-z0-9-]{3,32}$/;

export const RESERVED_SLUGS = new Set([
  "www",
  "api",
  "app",
  "admin",
  "vellano",
  "mail",
  "platform",
  "status",
  "docs",
  "stockroom",
]);

export function slugify(input: string): string {
  return input
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/\(pty\)|\bltd\b|\bcc\b|\binc\b/g, " ")
    .replace(/&/g, " and ")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 32)
    .replace(/-+$/g, "");
}

export type SlugCheck = { ok: true } | { ok: false; reason: "invalid" | "reserved" | "short" };

export function checkSlug(slug: string): SlugCheck {
  if (slug.length < 3) return { ok: false, reason: "short" };
  if (!SLUG_PATTERN.test(slug) || slug.startsWith("-") || slug.endsWith("-")) {
    return { ok: false, reason: "invalid" };
  }
  if (RESERVED_SLUGS.has(slug)) return { ok: false, reason: "reserved" };
  return { ok: true };
}

export function passwordStrength(password: string): 0 | 1 | 2 | 3 | 4 {
  if (!password) return 0;
  let score = 0;
  if (password.length >= 12) score += 1;
  if (password.length >= 16) score += 1;
  if (/[a-z]/.test(password) && /[A-Z]/.test(password)) score += 1;
  if (/\d/.test(password) || /[^\w\s]/.test(password)) score += 1;
  return Math.min(4, score) as 0 | 1 | 2 | 3 | 4;
}
