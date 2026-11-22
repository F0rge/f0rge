#!/usr/bin/env node
// Build one deployable Project's image for its Host's architecture, start it and
// expect its health endpoint to answer. IMAGE_PUSH=true also pushes it.
//
//   node .github/scripts/image.mjs <project root>        (Nx target: `image`)
//
// Everything comes from the Project's `metadata.deploy` block in project.json:
//   host                  railway → linux/amd64, pi → linux/arm64 (IMAGE_PLATFORM overrides it for a
//                         quick local check on another architecture; CI never sets it)
//   build.context         build context (default: repository root)
//   build.args            public build arguments (the image is public: never a secret)
//   check.port            port the container listens on
//   check.path            health path (default: the first service's healthcheckPath)
//   check.migrate         run before start (default: the first service's preDeployCommand)
//   check.migrateOutput   text the migrate output must contain, so a step that never ran fails the check
//   check.postgres/redis  image of a throwaway database, reachable as `postgres` (f0rge:f0rge, database f0rge) / `redis`
//   check.env             environment for the migrate and start containers
import { execFileSync, spawnSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';

// Railway runs a pre-deploy or start command without a shell (quotes still group words; `a && b`
// ran only `a`). Split it into words here too, so shell syntax is not quietly honoured in CI.
// ponytail: quotes and whitespace only, no escapes; a command needing more runs `/bin/sh -c '…'` itself.
export const words = (command = '') => (command.match(/(?:[^\s'"]+|'[^']*'|"[^"]*")+/g) ?? [])
  .map((word) => word.replace(/'([^']*)'|"([^"]*)"/g, '$1$2'));

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const root = process.argv[2]?.replace(/\/+$/, '');
  if (!root) throw new Error('Usage: image.mjs <project root>');
  const { name, metadata } = JSON.parse(readFileSync(`${root}/project.json`, 'utf8'));
  const { host, services, build = {}, check } = metadata.deploy;
  if (!check?.port) throw new Error(`${name}: metadata.deploy.check.port is required`);

  const docker = (...args) => execFileSync('docker', args, { stdio: 'inherit' });
  const quiet = (...args) => execFileSync('docker', args, { encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] }).trim();
  const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  const commit = process.env.GITHUB_SHA ?? execFileSync('git', ['rev-parse', 'HEAD'], { encoding: 'utf8' }).trim();
  const image = `ghcr.io/f0rge/${name}:${commit}`;
  const platform = process.env.IMAGE_PLATFORM ?? `linux/${host === 'pi' ? 'arm64' : 'amd64'}`;

  // ponytail: no layer cache between runs, every build is cold. Add a registry cache if build time hurts.
  docker(
    'build', '--platform', platform, '--file', `${root}/Dockerfile`, '--tag', image,
    // The source label links the GHCR package to this repository.
    '--label', 'org.opencontainers.image.source=https://github.com/F0rge/f0rge',
    '--build-arg', `SOURCE_COMMIT=${commit}`,
    ...Object.entries(build.args ?? {}).flatMap(([key, value]) => ['--build-arg', `${key}=${value}`]),
    build.context ?? '.',
  );

  const id = `check-${name}-${process.pid}`;
  const env = Object.entries(check.env ?? {}).flatMap(([key, value]) => ['--env', `${key}=${value}`]);
  const service = services[0];
  const migrate = words(check.migrate ?? service.preDeployCommand);
  const start = words(service.startCommand);
  const path = check.path ?? service.healthcheckPath;
  const started = [];
  let healthy = false;
  docker('network', 'create', id);
  try {
    if (check.postgres) {
      started.push(`${id}-postgres`);
      docker('run', '--detach', '--name', `${id}-postgres`, '--network', id, '--network-alias', 'postgres',
        '--env', 'POSTGRES_USER=f0rge', '--env', 'POSTGRES_PASSWORD=f0rge', '--env', 'POSTGRES_DB=f0rge', check.postgres);
      // TCP only answers once initialisation has finished and the real server is up.
      for (let attempt = 0; ; attempt++) {
        try { quiet('exec', `${id}-postgres`, 'psql', '--host=127.0.0.1', '--username=f0rge', '--dbname=f0rge', '--command=select 1'); break; }
        catch (error) { if (attempt === 60) throw new Error(`${name}: throwaway Postgres did not start`); await sleep(1000); }
      }
    }
    if (check.redis) {
      started.push(`${id}-redis`);
      docker('run', '--detach', '--name', `${id}-redis`, '--network', id, '--network-alias', 'redis', check.redis);
    }
    // Railway's docs do not say whether a pre-deploy command replaces the image's entrypoint or is
    // passed to it; this check passes it to the entrypoint. A command that names an absolute path
    // (DasKasas commerce) works either way.
    if (migrate.length) {
      const run = spawnSync('docker', ['run', '--rm', '--platform', platform, '--network', id, ...env, image, ...migrate],
        { encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'], maxBuffer: 64 * 1024 * 1024 });
      const output = `${run.stdout ?? ''}${run.stderr ?? ''}`;
      process.stdout.write(output);
      if (run.status !== 0) throw new Error(`${name}: migrate exited ${run.status ?? run.error?.message}`);
      if (check.migrateOutput && !output.includes(check.migrateOutput))
        throw new Error(`${name}: migrate output lacks "${check.migrateOutput}"`);
    }
    started.push(id);
    try {
      // Railway's start command replaces the image's entrypoint.
      docker('run', '--detach', '--name', id, '--platform', platform, '--network', id, ...env,
        '--publish', `127.0.0.1::${check.port}`, ...(start.length ? ['--entrypoint', start[0], image, ...start.slice(1)] : [image]));
      // `docker port` throws when the container has already exited.
      const url = `http://${quiet('port', id, String(check.port)).split('\n')[0]}${path}`;
      for (let attempt = 0; attempt < 90 && !healthy; attempt++) {
        if (quiet('inspect', '--format', '{{.State.Running}}', id) !== 'true') break;
        healthy = await fetch(url, { signal: AbortSignal.timeout(5000) }).then((response) => response.ok, () => false);
        if (!healthy) await sleep(2000);
      }
      if (!healthy) throw new Error(`${name}: ${path} on port ${check.port} did not answer`);
    } catch (error) {
      try { docker('logs', '--tail', '200', id); } catch { /* the container may never have been created */ }
      throw error;
    }
    console.log(`${name}: ${image} (${platform}) answered ${path}`);
  } finally {
    for (const container of started) docker('rm', '--force', '--volumes', container);
    docker('network', 'rm', id);
  }
  if (process.env.IMAGE_PUSH === 'true') docker('push', image);
}
