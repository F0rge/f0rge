type Environment = Record<string, string | undefined>

/** Medusa local-file directory on the commerce image. A Railway volume mounts here. */
export const HOSTED_UPLOAD_DIR = '/app/apps/storefront/commerce/.medusa/server/static'

/**
 * Public base URL the local file provider writes onto product images.
 * Railway's public domain keeps gallery URLs on this service after upload.
 * Local development stays on the Medusa default.
 */
export function publicFileBackendUrl(env: Environment): string {
  const railwayHost = env.RAILWAY_PUBLIC_DOMAIN?.trim()
  if (railwayHost) return `https://${railwayHost}/static`
  return 'http://localhost:9000/static'
}

export function hostedLocalFileOptions(env: Environment): {
  backend_url: string
  upload_dir?: string
  private_upload_dir?: string
} {
  const backend_url = publicFileBackendUrl(env)
  if (!env.RAILWAY_PUBLIC_DOMAIN?.trim()) return { backend_url }
  return {
    backend_url,
    upload_dir: HOSTED_UPLOAD_DIR,
    private_upload_dir: HOSTED_UPLOAD_DIR,
  }
}
