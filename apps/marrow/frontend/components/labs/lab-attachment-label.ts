const HEX_STEM = /^[a-f0-9]{32,}$/i

/** Human filename from lab.source_path, or null for hashes / upload keys. */
export function humanSourceFilename(
  sourcePath: string | null | undefined,
): string | null {
  const path = sourcePath?.trim()
  if (!path) return null
  if (path.startsWith('upload:')) return null
  const base = path.split(/[/\\]/).pop() ?? path
  if (!base) return null
  const stem = base.replace(/\.[A-Za-z0-9]+$/, '')
  if (HEX_STEM.test(stem) || HEX_STEM.test(base)) return null
  return base
}
