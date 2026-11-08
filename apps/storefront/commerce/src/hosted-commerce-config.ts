import { isHostedRuntime } from './runtime-safety'

type Environment = Record<string, string | undefined>

/** Fail closed instead of running a hosted Medusa instance with fake queue infrastructure or fallback secrets. */
export function assertHostedCommerceConfig(env: Environment): void {
  if (!isHostedRuntime(env)) return

  const required = ['DATABASE_URL', 'REDIS_URL']
  const missing = required.filter((name) => !env[name]?.trim())
  if (missing.length) {
    throw new Error(`Hosted DasKasas requires ${missing.join(', ')}`)
  }

  const weakSecrets = ['JWT_SECRET', 'COOKIE_SECRET', 'STOREFRONT_BFF_SECRET']
    .filter((name) => (env[name]?.trim().length ?? 0) < 32)
  if (weakSecrets.length) {
    throw new Error(`Hosted DasKasas requires at least 32 characters for ${weakSecrets.join(', ')}`)
  }
}
