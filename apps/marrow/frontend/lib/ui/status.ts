/**
 * Single source of truth for status / flag / illustration colour classes.
 * Chrome stays on semantic tokens (bg-primary, bg-card, …). Domain colour
 * for data (ok/warn/info, scales, lab flags, diet, treatment types) lives here.
 *
 * Red/terracotta (--destructive, --chart-2) is for actual negatives only —
 * never category labels or selected toggles. Diet flags are equivalent tags:
 * selected chrome is ink; small pills share one warn wash.
 *
 * Uses Tailwind classes that map to skin CSS vars (--ok, --warn, --info,
 * --chart-*, --destructive, --muted). No zinc/amber/teal/emerald palette.
 *
 * Split across status-core / status-domain / status-chrome; this barrel is
 * the public import path (`@/lib/ui/status`).
 */

export * from './status-core'
export * from './status-domain'
export * from './status-chrome'
