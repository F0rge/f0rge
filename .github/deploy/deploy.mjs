#!/usr/bin/env node
// Releases one App at one commit on its Host. If that fails, puts every service it touched
// back on the image it ran before, then exits non-zero.
//   node .github/deploy/deploy.mjs --app <app> --commit <40-char sha>
// Env: Railway Apps: RAILWAY_TOKEN (project token); Pi Apps: COOLIFY_URL, COOLIFY_TOKEN.
// Optional: DEPLOY_TIMEOUT_SECONDS (per service, default 900),
//           DEPLOY_SETTLE_SECONDS (Pi: how long a container must stay up and not unhealthy, default 90).
import { parseArgs } from 'node:util';
import { pathToFileURL } from 'node:url';
import { listApps } from './deployables.mjs';

const POLL_SECONDS = 10;
const HOST_ENV = { railway: ['RAILWAY_TOKEN'], pi: ['COOLIFY_URL', 'COOLIFY_TOKEN'] };

// Each Host answers the same four questions:
//   find(service) → the provider id of the service (undefined: none); throws if that is ambiguous
//   read(id) → { image } the service is configured to run now (undefined: none yet)
//   start(id, service, image, rollback, now) → a handle for the deployment it started (null: nothing to do)
//   status(id, handle) → 'pending' | 'ok' | 'failed'; called every POLL_SECONDS
const hosts = {
  async railway(env, fetch) {
    const gql = async (query, variables = {}) => {
      const res = await fetch('https://backboard.railway.com/graphql/v2', {
        method: 'POST',
        headers: { 'content-type': 'application/json', 'project-access-token': env.RAILWAY_TOKEN },
        body: JSON.stringify({ query, variables }),
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok || body.errors)
        throw new Error(`Railway: ${body.errors?.map((error) => error.message).join('; ') ?? `HTTP ${res.status}`}`);
      return body.data;
    };
    // A project token is bound to one project and one environment; ask it which.
    const { projectId, environmentId } = (await gql('query { projectToken { projectId environmentId } }')).projectToken;
    const { project } = await gql('query($id:String!){ project(id:$id){ services { edges { node { id name } } } } }', { id: projectId });
    const read = async (service) => {
      const { serviceInstance } = await gql(
        'query($service:String!,$env:String!){ serviceInstance(serviceId:$service,environmentId:$env){ source { image } latestDeployment { id status } } }',
        { service, env: environmentId },
      );
      return { image: serviceInstance.source?.image ?? undefined, deployment: serviceInstance.latestDeployment };
    };
    const ids = new Map(project.services.edges.map(({ node }) => [node.name, node.id]));
    return {
      find: (service) => ids.get(service.name),
      read,
      async start(id, service, image, rollback, now) {
        // An unchanged patch starts no deployment, so there would be nothing to wait for.
        if (now.image === image) {
          if (now.deployment?.status === 'SUCCESS') return null;
          throw new Error(`${service.name} is already set to ${image}, but its latest deployment is ${now.deployment?.status ?? 'missing'}; redeploy it on Railway`);
        }
        const patch = {
          services: {
            [id]: {
              source: { repo: null, branch: null, commitSha: null, image, autoUpdates: { type: 'disabled' } },
              deploy: {
                // An older image must not run its migrations against a newer schema.
                preDeployCommand: service.preDeployCommand && !rollback ? [service.preDeployCommand] : [],
                startCommand: service.startCommand ?? null,
                healthcheckPath: service.healthcheckPath ?? null,
              },
            },
          },
        };
        await gql(
          'mutation($env:String!,$patch:EnvironmentConfig!,$message:String!){ environmentPatchCommit(environmentId:$env,patch:$patch,commitMessage:$message,skipDeploys:false) }',
          { env: environmentId, patch, message: `${rollback ? 'Roll back' : 'Release'} ${service.name} ${image.split(/[:@]/).pop().slice(0, 12)}` },
        );
        return { before: now.deployment?.id };
      },
      async status(id, { before }) {
        const { deployment } = await read(id);
        if (!deployment || deployment.id === before) return 'pending';
        if (deployment.status === 'SUCCESS') return 'ok';
        return ['FAILED', 'CRASHED', 'REMOVED', 'SKIPPED'].includes(deployment.status) ? 'failed' : 'pending';
      },
    };
  },

  async pi(env, fetch) {
    const api = async (path, init = {}) => {
      const res = await fetch(`${env.COOLIFY_URL.replace(/\/+$/, '')}/api/v1${path}`, {
        ...init,
        headers: { authorization: `Bearer ${env.COOLIFY_TOKEN}`, accept: 'application/json', 'content-type': 'application/json' },
      });
      // Path only: the Coolify address is not public and this log is.
      if (!res.ok) throw new Error(`Coolify: ${init.method ?? 'GET'} ${path.split('?')[0]} answered HTTP ${res.status}`);
      return res.json();
    };
    // ponytail: a fixed window. Coolify only learns a container's state about once a minute, and
    // reports "running:healthy" while a HEALTHCHECK is still in its start period, so "healthy" is
    // believed only once it has held this long. Raise it if a HEALTHCHECK takes longer to fail.
    const settle = Math.max(1, Math.ceil(Number(env.DEPLOY_SETTLE_SECONDS ?? 90) / POLL_SECONDS));
    // Only "Docker image" applications count, so an App not yet switched in Coolify is "not found".
    const applications = (await api('/applications')).filter((application) => application.build_pack === 'dockerimage');
    const before = new Map(applications.map((application) => [application.uuid, application]));
    return {
      // Fail closed: a Release must change exactly one application, and only one that runs this Project's image.
      find(service) {
        const matches = applications.filter((application) => application.name === service.name);
        if (matches.length > 1) throw new Error(`${matches.length} Docker image applications on the Pi are named ${service.name}; nothing was released`);
        if (matches[0] && matches[0].docker_registry_image_name !== service.repository)
          throw new Error(`${service.name} on the Pi runs ${matches[0].docker_registry_image_name}, not ${service.repository}; nothing was released`);
        return matches[0]?.uuid;
      },
      async read(uuid) {
        const { docker_registry_image_name: name, docker_registry_image_tag: tag } = before.get(uuid);
        return { image: tag ? `${name}:${tag}` : undefined };
      },
      async start(uuid, service, image) {
        // Coolify rejects unknown fields; the tag is all a Release changes.
        await api(`/applications/${uuid}`, { method: 'PATCH', body: JSON.stringify({ docker_registry_image_tag: image.split(':').pop() }) });
        const { deployments } = await api(`/deploy?uuid=${uuid}`);
        const deployment = deployments?.[0]?.deployment_uuid;
        if (!deployment) throw new Error(`Coolify queued no deployment for ${service.name}: ${deployments?.[0]?.message ?? 'no reason given'}`);
        return { deployment, finished: false, good: 0, bad: 0 };
      },
      async status(uuid, handle) {
        if (!handle.finished) {
          const { status } = await api(`/deployments/${handle.deployment}`);
          if (['failed', 'cancelled-by-user'].includes(status)) return 'failed';
          handle.finished = status === 'finished';
          return 'pending';
        }
        // "finished" only means the container was started. Its health is the application's status:
        // running:healthy | running:unknown (no HEALTHCHECK) | running:unhealthy | exited |
        // restarting:… | degraded:… | starting:…
        const { status = '' } = await api(`/applications/${uuid}`);
        handle.good = ['running:healthy', 'running:unknown'].includes(status) ? handle.good + 1 : 0;
        handle.bad = /^(exited|restarting|degraded)|unhealthy/.test(status) ? handle.bad + 1 : 0;
        if (handle.bad >= 2) return 'failed'; // twice: one read can still describe the old container
        return handle.good >= settle ? 'ok' : 'pending';
      },
    };
  },
};

export async function deploy({
  app,
  commit,
  root = process.cwd(),
  env = process.env,
  fetch = globalThis.fetch,
  sleep = (seconds) => new Promise((resolve) => setTimeout(resolve, seconds * 1000)),
  log = console.log,
}) {
  if (!/^[0-9a-f]{40}$/.test(commit ?? '')) throw new Error('--commit must be a full 40-character commit sha');
  const entry = listApps(root).find((candidate) => candidate.app === app);
  if (!entry) throw new Error(`"${app}" is not a deployable App (no Project with scope:${app} has a deploy block)`);

  // Fail closed: everything below this block is checked before anything changes on the Host.
  const unset = HOST_ENV[entry.host].filter((name) => !env[name]);
  if (unset.length) throw new Error(`${unset.join(', ')} not set for App ${app}; nothing was released`);
  const services = entry.projects
    .flatMap((project) => project.services.map((service) => ({ ...service, repository: project.image, image: `${project.image}:${commit}` })))
    .sort((a, b) => Boolean(b.preDeployCommand) - Boolean(a.preDeployCommand)); // migrations first
  const unsupported = services.filter((service) => entry.host === 'pi' && (service.preDeployCommand || service.startCommand));
  if (unsupported.length)
    throw new Error(`preDeployCommand/startCommand are not sent to the Pi (${unsupported.map((service) => service.name).join(', ')}); nothing was released`);
  const host = await hosts[entry.host](env, fetch);
  const ids = new Map(services.map((service) => [service.name, host.find(service)]));
  const missing = services.filter((service) => !ids.get(service.name));
  if (missing.length)
    throw new Error(`${missing.map((service) => service.name).join(', ')} not found on ${entry.host} for App ${app}; nothing was released`);

  const timeout = Number(env.DEPLOY_TIMEOUT_SECONDS) || 900;
  const touched = []; // { service, previous }: what to put back, recorded before each change
  const release = async (service, image, rollback = false) => {
    const id = ids.get(service.name);
    const now = await host.read(id);
    if (!rollback) touched.push({ service, previous: now.image });
    const handle = await host.start(id, service, image, rollback, now);
    if (!handle) return log(`${service.name}: already running ${image}`);
    log(`${service.name}: ${rollback ? 'putting back' : 'releasing'} ${image}`);
    for (let waited = 0; waited < timeout; waited += POLL_SECONDS) {
      await sleep(POLL_SECONDS);
      const status = await host.status(id, handle).catch(() => 'pending'); // one bad poll is not a failed Release
      if (status === 'ok') return log(`${service.name}: healthy`);
      if (status === 'failed') throw new Error(`${service.name} failed to become healthy on ${image}`);
    }
    throw new Error(`${service.name} was not healthy within ${timeout}s on ${image}`);
  };

  try {
    for (const service of services) await release(service, service.image);
    log(`Released ${app} at ${commit}`);
  } catch (error) {
    log(`Release of ${app} failed: ${error.message}`);
    for (const { service, previous } of touched.reverse()) {
      if (!previous || previous === service.image) {
        log(`${service.name}: ran no other image before this Release; left as it is`);
        continue;
      }
      await release(service, previous, true).catch((rollbackError) => log(`${service.name}: rollback failed: ${rollbackError.message}`));
    }
    throw new Error(`Release of ${app} at ${commit} failed`);
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const { values } = parseArgs({ options: { app: { type: 'string' }, commit: { type: 'string' } } });
  deploy(values).catch((error) => {
    console.error(error.message);
    process.exit(1);
  });
}
