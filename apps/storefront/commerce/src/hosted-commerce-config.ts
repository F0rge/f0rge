type Environment = Record<string, string | undefined>

/** Fail closed instead of running a hosted Medusa instance with fake queue infrastructure or fallback secrets. */
export function assertHostedCommerceConfig(env: Environment): void {
  const hostedRuntime = env.STOREFRONT_RUNTIME_KIND === 'hosted' || [
    'RAILWAY_ENVIRONMENT_NAME', 'RAILWAY_PROJECT_ID', 'RAILWAY_SERVICE_ID',
    'VERCEL', 'VERCEL_ENV', 'FLY_APP_NAME', 'RENDER', 'K_SERVICE',
  ].some((name) => !!env[name])
  if (!hostedRuntime) return

  const required = ['DATABASE_URL', 'REDIS_URL']
  const missing = required.filter((name) => !env[name]?.trim())
  if (missing.length) {
    throw new Error(`Hosted Storefront requires ${missing.join(', ')}`)
  }

  const weakSecrets = ['JWT_SECRET', 'COOKIE_SECRET', 'STOREFRONT_BFF_SECRET']
    .filter((name) => (env[name]?.trim().length ?? 0) < 32)
  if (weakSecrets.length) {
    throw new Error(`Hosted Storefront requires at least 32 characters for ${weakSecrets.join(', ')}`)
  }
}
