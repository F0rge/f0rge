import { existsSync } from "node:fs";

type Environment = Record<string, string | undefined>;

// The supported release image installs this root-owned marker outside the app's
// writable tree. Runtime environment overrides cannot make that image local.
const HOSTED_ARTIFACT_MARKER = "/usr/local/share/daskasas/hosted-artifact";
const LOOPBACK_HOSTS = new Set(["localhost", "127.0.0.1", "::1", "[::1]"]);

function loopbackUrl(value: string | undefined, protocols: string[]): boolean {
  if (!value?.trim()) return false;
  try {
    const url = new URL(value);
    return protocols.includes(url.protocol) && LOOPBACK_HOSTS.has(url.hostname);
  } catch {
    return false;
  }
}

function loopbackOrigins(value: string | undefined): boolean {
  return !!value?.trim() && value.split(",").every((origin) => loopbackUrl(origin.trim(), ["http:", "https:"]));
}

function explicitLocalCommand(): boolean {
  const [, , command, ...args] = process.argv;
  // These supported commands do not open a Medusa HTTP listener.
  if (["exec", "db:migrate", "db:create", "db:sync"].includes(command)) return true;
  if (command !== "start" && command !== "develop") return false;

  // CLI flags override HOST. Require the actual server command's explicit
  // binding, and reject overrides or ambiguous options.
  let host: string | undefined;
  for (let index = 0; index < args.length; index += 1) {
    const argument = args[index];
    if (argument === "--host" || argument === "-H" || argument.startsWith("--host=")) {
      if (host !== undefined) return false;
      host = argument.startsWith("--host=") ? argument.slice(7) : args[++index];
      if (!LOOPBACK_HOSTS.has(host ?? "")) return false;
    } else if (argument === "--port" || argument === "-p" || argument.startsWith("--port=")) {
      const port = argument.startsWith("--port=") ? argument.slice(7) : args[++index];
      if (!port || !/^\d+$/.test(port) || Number(port) < 1 || Number(port) > 65535) return false;
    } else if (/^--(?:no-)?(?:types|lint|fix)(?:=(?:true|false))?$/.test(argument)) {
      if (args[index + 1] === "true" || args[index + 1] === "false") index += 1;
    } else {
      return false;
    }
  }
  return host !== undefined;
}

/** Only an explicit loopback-bound local/test setup may use development fallbacks. */
export function isHostedRuntime(env: Environment): boolean {
  if (existsSync(HOSTED_ARTIFACT_MARKER)) return true;
  const providerRuntime = [
    "RAILWAY_ENVIRONMENT_NAME", "RAILWAY_PROJECT_ID", "RAILWAY_SERVICE_ID",
    "VERCEL", "VERCEL_ENV", "RENDER", "K_SERVICE",
  ].some((name) => !!env[name]);
  if (providerRuntime) return true;

  const localMode = (env.STOREFRONT_RUNTIME_KIND === "local" && env.NODE_ENV === "development") ||
    (env.STOREFRONT_RUNTIME_KIND === "test" && env.NODE_ENV === "test");
  const isolated = localMode && explicitLocalCommand() && LOOPBACK_HOSTS.has(env.HOST ?? "") &&
    loopbackUrl(env.DATABASE_URL, ["postgres:", "postgresql:"]) &&
    loopbackUrl(env.REDIS_URL, ["redis:", "rediss:"]) &&
    loopbackUrl(env.STOREFRONT_PUBLIC_URL, ["http:", "https:"]) &&
    [env.STORE_CORS, env.ADMIN_CORS, env.AUTH_CORS].every(loopbackOrigins) &&
    (!env.FIRSTOUT_OPS_URL || loopbackUrl(env.FIRSTOUT_OPS_URL, ["http:", "https:"]));
  return !isolated;
}
