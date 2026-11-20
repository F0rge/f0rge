import assert from 'node:assert/strict';
import { mkdirSync, mkdtempSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { test } from 'node:test';
import { deploy } from './deploy.mjs';

const NEW = 'a'.repeat(40);
const OLD = 'b'.repeat(40);
const MIGRATE = 'run-migrations';
const image = (project, sha) => `ghcr.io/f0rge/${project}:${sha}`;

function repo(host) {
  const root = mkdtempSync(join(tmpdir(), 'deploy-'));
  const projects = {
    // The frontend sorts first by name; the API must still be released first because it migrates.
    'apps/shop/frontend': { name: 'shop-frontend', tags: ['scope:shop'], metadata: { deploy: { host, services: [{ name: 'shop-frontend', healthcheckPath: '/healthz', port: 3000 }] } } },
    'apps/shop/backend': {
      name: 'shop-backend',
      tags: ['scope:shop'],
      metadata: { deploy: { host, services: [{ name: 'shop-api', healthcheckPath: '/ready', ...(host === 'railway' && { preDeployCommand: MIGRATE }) }] } },
    },
  };
  for (const [dir, json] of Object.entries(projects)) {
    mkdirSync(join(root, dir), { recursive: true });
    writeFileSync(join(root, dir, 'project.json'), JSON.stringify(json));
  }
  return root;
}

const reply = (body, status = 200) => ({ ok: status < 400, status, json: async () => body });

// Railway: `running` is the image each service is configured with; every patch starts a
// deployment whose final status is `outcome(image)`.
function railway({ outcome = () => 'SUCCESS', services = { 'shop-api': 'svc-api', 'shop-frontend': 'svc-web' }, running, latest = {} } = {}, calls) {
  running ??= { 'svc-api': image('shop-backend', OLD), 'svc-web': image('shop-frontend', OLD) };
  let next = 1;
  return (url, init) => {
    assert.equal(url, 'https://backboard.railway.com/graphql/v2');
    assert.equal(init.headers['project-access-token'], 'railway-token');
    const { query, variables } = JSON.parse(init.body);
    if (query.includes('projectToken')) return reply({ data: { projectToken: { projectId: 'proj', environmentId: 'env' } } });
    if (query.includes('project(')) {
      assert.equal(variables.id, 'proj');
      return reply({ data: { project: { services: { edges: Object.entries(services).map(([name, id]) => ({ node: { id, name } })) } } } });
    }
    if (query.includes('serviceInstance'))
      return reply({ data: { serviceInstance: { source: { image: running[variables.service] ?? null }, latestDeployment: latest[variables.service] ?? null } } });
    assert.match(query, /environmentPatchCommit\(environmentId:\$env,patch:\$patch,commitMessage:\$message,skipDeploys:false\)/);
    assert.equal(variables.env, 'env');
    for (const [id, config] of Object.entries(variables.patch.services)) {
      calls.push({ id, ...config });
      running[id] = config.source.image;
      latest[id] = { id: `dep-${next++}`, status: outcome(config.source.image) };
    }
    return reply({ data: { environmentPatchCommit: 'commit-id' } });
  };
}

// Coolify: every deploy trigger starts a deployment that walks through `statuses(tag)`; after it,
// the application reports `health(tag, uuid)`, one entry per poll, the last one repeating.
const application = (name, uuid, build_pack, tag, project = name) => ({ name, uuid, build_pack, docker_registry_image_name: `ghcr.io/f0rge/${project}`, docker_registry_image_tag: tag });
function coolify({ statuses = () => ['queued', 'in_progress', 'finished'], health = () => ['running:healthy'], applications } = {}, calls) {
  applications ??= [
    application('shop-api', 'old-api', 'dockerfile'), // the not-yet-retired old application
    application('shop-api', 'app-api', 'dockerimage', OLD, 'shop-backend'),
    application('shop-frontend', 'app-web', 'dockerimage', OLD),
  ];
  const deployments = {};
  const healths = {};
  const step = (queue) => (queue.length > 1 ? queue.shift() : queue[0]);
  let next = 1;
  return (url, init) => {
    assert.equal(init.headers.authorization, 'Bearer coolify-token');
    const path = url.replace('https://coolify.test/api/v1', '');
    const method = init.method ?? 'GET';
    if (path === '/applications') return reply(structuredClone(applications));
    const [, uuid] = path.match(/^\/applications\/([\w-]+)$/) ?? [];
    const found = applications.find((candidate) => candidate.uuid === uuid);
    if (found && method === 'PATCH') {
      calls.push({ patch: uuid, body: JSON.parse(init.body) });
      found.docker_registry_image_tag = JSON.parse(init.body).docker_registry_image_tag;
      return reply({ uuid });
    }
    if (found && method === 'GET') {
      calls.push({ health: uuid });
      return reply({ uuid, status: step(healths[uuid]) });
    }
    const [, deployed] = path.match(/^\/deploy\?uuid=([\w-]+)$/) ?? [];
    if (deployed && method === 'GET') {
      const tag = applications.find((candidate) => candidate.uuid === deployed).docker_registry_image_tag;
      const deployment = `dep-${next++}`;
      deployments[deployment] = [...statuses(tag)];
      healths[deployed] = [...health(tag, deployed)];
      calls.push({ deploy: deployed, tag });
      return reply({ deployments: [{ message: 'queued', resource_uuid: deployed, deployment_uuid: deployment }] });
    }
    const [, polled] = path.match(/^\/deployments\/([\w-]+)$/) ?? [];
    if (polled && method === 'GET') return reply({ status: step(deployments[polled]) });
    throw new Error(`unexpected Coolify request ${method} ${path}`);
  };
}

function run(host, { provider, env = {} } = {}) {
  const calls = [];
  const logs = [];
  let requests = 0;
  const fakes = { 'https://backboard.railway.com': railway(provider, calls), 'https://coolify.test': coolify(provider, calls) };
  const result = deploy({
    app: 'shop',
    commit: NEW,
    root: repo(host),
    // 30 s of settling is three polls.
    env: { RAILWAY_TOKEN: 'railway-token', COOLIFY_URL: 'https://coolify.test/', COOLIFY_TOKEN: 'coolify-token', DEPLOY_SETTLE_SECONDS: '30', ...env },
    fetch: async (url, init = {}) => {
      requests += 1;
      return fakes[new URL(url).origin](url, init);
    },
    sleep: async () => {},
    log: (line) => logs.push(line),
  });
  return { result, calls, logs, requests: () => requests };
}

const source = (project, sha) => ({ repo: null, branch: null, commitSha: null, image: image(project, sha), autoUpdates: { type: 'disabled' } });
const patches = (calls) => calls.filter((call) => call.id).map((call) => [call.id, call.source.image, call.deploy.preDeployCommand]);
const deploys = (calls) => calls.filter((call) => call.deploy);
const healthPolls = (calls, uuid) => calls.filter((call) => call.health === uuid).length;

test('Railway: releases every service at the commit, the migrating one first', async () => {
  const { result, calls } = run('railway');
  await result;
  assert.deepEqual(calls, [
    { id: 'svc-api', source: source('shop-backend', NEW), deploy: { preDeployCommand: [MIGRATE], startCommand: null, healthcheckPath: '/ready' } },
    { id: 'svc-web', source: source('shop-frontend', NEW), deploy: { preDeployCommand: [], startCommand: null, healthcheckPath: '/healthz' } },
  ]);
});

test('Railway: a service already running the commit is left alone', async () => {
  const calls = [];
  const provider = railway({}, calls);
  const options = { app: 'shop', commit: NEW, root: repo('railway'), env: { RAILWAY_TOKEN: 'railway-token' }, fetch: async (url, init) => provider(url, init), sleep: async () => {}, log: () => {} };
  await deploy(options);
  await deploy(options);
  assert.equal(calls.length, 2, 'the second Release patches nothing');
});

test('Railway: a service already set to the commit image is not patched, so nothing waits for a deployment that never starts', async () => {
  const running = { 'svc-api': image('shop-backend', NEW), 'svc-web': image('shop-frontend', NEW) };
  const { result, calls, logs } = run('railway', { provider: { running, latest: { 'svc-api': { id: 'dep-0', status: 'SUCCESS' }, 'svc-web': { id: 'dep-0', status: 'SUCCESS' } } } });
  await result;
  assert.deepEqual(calls, []);
  assert.ok(logs.includes(`shop-frontend: already running ${image('shop-frontend', NEW)}`));

  // Set to the image but not running it: a patch would change nothing, so fail now instead of after the timeout.
  const failed = run('railway', { provider: { running, latest: { 'svc-api': { id: 'dep-0', status: 'CRASHED' } } } });
  await assert.rejects(failed.result, /Release of shop at a{40} failed/);
  assert.deepEqual(failed.calls, []);
  assert.ok(failed.logs.some((line) => line.includes('shop-api is already set to') && line.includes('latest deployment is CRASHED')));
});

test('Railway: a deployment that never finishes times out and rolls back', async () => {
  const { result, calls, logs } = run('railway', {
    provider: { outcome: (deployed) => (deployed === image('shop-backend', NEW) ? 'DEPLOYING' : 'SUCCESS') },
    env: { DEPLOY_TIMEOUT_SECONDS: '30' },
  });
  await assert.rejects(result, /Release of shop at a{40} failed/);
  assert.deepEqual(patches(calls), [
    ['svc-api', image('shop-backend', NEW), [MIGRATE]],
    ['svc-api', image('shop-backend', OLD), []],
  ]);
  assert.ok(logs.includes(`Release of shop failed: shop-api was not healthy within 30s on ${image('shop-backend', NEW)}`));
});

test('Railway: a rollback that fails is logged, the other touched services are still put back, and the Release fails', async () => {
  const { result, calls, logs } = run('railway', { provider: { outcome: (deployed) => (deployed === image('shop-backend', NEW) ? 'SUCCESS' : 'FAILED') } });
  await assert.rejects(result, /Release of shop at a{40} failed/);
  assert.deepEqual(patches(calls), [
    ['svc-api', image('shop-backend', NEW), [MIGRATE]],
    ['svc-web', image('shop-frontend', NEW), []],
    ['svc-web', image('shop-frontend', OLD), []],
    ['svc-api', image('shop-backend', OLD), []],
  ]);
  assert.ok(logs.includes(`shop-frontend: rollback failed: shop-frontend failed to become healthy on ${image('shop-frontend', OLD)}`));
  assert.ok(logs.includes(`shop-api: rollback failed: shop-api failed to become healthy on ${image('shop-backend', OLD)}`));
});

test('Railway: an unhealthy Release puts each touched service back on the image it ran, without migrating', async () => {
  // The API ran a digest-pinned image from another repository; that exact reference must come back.
  const pinned = `ghcr.io/f0rge/legacy-api@sha256:${'c'.repeat(64)}`;
  const { result, calls, logs } = run('railway', {
    provider: { running: { 'svc-api': pinned, 'svc-web': image('shop-frontend', OLD) }, outcome: (deployed) => (deployed === image('shop-frontend', NEW) ? 'FAILED' : 'SUCCESS') },
  });
  await assert.rejects(result, /Release of shop at a{40} failed/);
  assert.deepEqual(patches(calls), [
    ['svc-api', image('shop-backend', NEW), [MIGRATE]],
    ['svc-web', image('shop-frontend', NEW), []],
    ['svc-web', image('shop-frontend', OLD), []],
    ['svc-api', pinned, []],
  ]);
  assert.ok(logs.includes(`shop-api: putting back ${pinned}`));
});

test('Railway: a service that ran no image before is left alone and the Release fails', async () => {
  // Both services still build from the repository; the API's first image never becomes healthy.
  const { result, calls, logs } = run('railway', { provider: { running: {}, outcome: () => 'CRASHED' } });
  await assert.rejects(result, /Release of shop at a{40} failed/);
  assert.deepEqual(patches(calls), [['svc-api', image('shop-backend', NEW), [MIGRATE]]]);
  assert.ok(logs.includes('shop-api: ran no other image before this Release; left as it is'));
});

test('Pi: sets the commit tag on each Docker-image application, deploys, and waits for it to stay healthy', async () => {
  const { result, calls } = run('pi');
  await result;
  assert.deepEqual(
    calls.filter((call) => !call.health),
    [
      { patch: 'app-api', body: { docker_registry_image_tag: NEW } },
      { deploy: 'app-api', tag: NEW },
      { patch: 'app-web', body: { docker_registry_image_tag: NEW } },
      { deploy: 'app-web', tag: NEW },
    ],
  );
  assert.equal(healthPolls(calls, 'app-api'), 3, 'healthy is believed after the settle window, not on first sight');
});

test('Pi: an image without a HEALTHCHECK passes once it has stayed running through the settle window', async () => {
  // One stale "exited" (the old container), then starting, then running with no health information.
  const { result, calls } = run('pi', { provider: { health: () => ['exited', 'starting:unknown', 'running:unknown'] } });
  await result;
  assert.equal(healthPolls(calls, 'app-api'), 5);
  assert.deepEqual(deploys(calls), [{ deploy: 'app-api', tag: NEW }, { deploy: 'app-web', tag: NEW }]);
});

test('Pi: a container that turns unhealthy fails the Release and the touched services go back to their tag', async () => {
  const { result, calls, logs } = run('pi', {
    // The frontend's new container starts, looks fine, then its HEALTHCHECK fails.
    provider: { health: (tag, uuid) => (tag === NEW && uuid === 'app-web' ? ['running:healthy', 'running:unhealthy'] : ['running:healthy']) },
  });
  await assert.rejects(result, /Release of shop at a{40} failed/);
  assert.deepEqual(deploys(calls), [
    { deploy: 'app-api', tag: NEW },
    { deploy: 'app-web', tag: NEW },
    { deploy: 'app-web', tag: OLD },
    { deploy: 'app-api', tag: OLD },
  ]);
  assert.ok(logs.includes(`Release of shop failed: shop-frontend failed to become healthy on ${image('shop-frontend', NEW)}`));
});

test('Pi: a crashed, restarting or degraded container, or a failed or cancelled deployment, rolls back too', async () => {
  const unhealthy = (status) => ({ health: (tag) => (tag === NEW ? [status] : ['running:unknown']) });
  const deployment = (...statuses) => ({ statuses: (tag) => (tag === NEW ? statuses : ['finished']) });
  for (const provider of [unhealthy('exited'), unhealthy('restarting:unknown'), unhealthy('degraded:unhealthy'), deployment('in_progress', 'failed'), deployment('queued', 'cancelled-by-user')]) {
    const { result, calls } = run('pi', { provider });
    await assert.rejects(result, /Release of shop at a{40} failed/);
    assert.deepEqual(deploys(calls), [
      { deploy: 'app-api', tag: NEW },
      { deploy: 'app-api', tag: OLD },
    ]);
  }
});

test('Pi: a first Release that never settles times out and has nothing to go back to', async () => {
  const { result, calls, logs } = run('pi', {
    // Created by hand with the commit to release as its tag, as the switch wizard says.
    provider: { applications: [application('shop-api', 'app-api', 'dockerimage', NEW, 'shop-backend'), application('shop-frontend', 'app-web', 'dockerimage', NEW)], health: () => ['starting:unknown'] },
    env: { DEPLOY_TIMEOUT_SECONDS: '60' },
  });
  await assert.rejects(result, /Release of shop at a{40} failed/);
  assert.deepEqual(deploys(calls), [{ deploy: 'app-api', tag: NEW }]);
  assert.ok(logs.some((line) => line.includes('not healthy within 60s')));
  assert.ok(logs.includes('shop-api: ran no other image before this Release; left as it is'));
});

test('a missing token fails closed before any request, and needs no GitHub token', async () => {
  for (const [host, name] of [['railway', 'RAILWAY_TOKEN'], ['pi', 'COOLIFY_TOKEN'], ['pi', 'COOLIFY_URL']]) {
    const { result, requests } = run(host, { env: { [name]: '' } });
    await assert.rejects(result, new RegExp(`${name} not set for App shop; nothing was released`));
    assert.equal(requests(), 0);
  }
});

test('a service name the Host does not have fails closed before any change', async () => {
  const railwayRun = run('railway', { provider: { services: { 'shop-api': 'svc-api' } } });
  await assert.rejects(railwayRun.result, /shop-frontend not found on railway for App shop; nothing was released/);
  assert.deepEqual(railwayRun.calls, []);

  // Still a Dockerfile application in Coolify: not switched yet.
  const piRun = run('pi', { provider: { applications: [application('shop-api', 'old-api', 'dockerfile'), application('shop-frontend', 'app-web', 'dockerimage', OLD)] } });
  await assert.rejects(piRun.result, /shop-api not found on pi for App shop; nothing was released/);
  assert.deepEqual(piRun.calls, []);
});

test('Pi: two Docker image applications with one name, or one running another image, fail closed before any change', async () => {
  const web = application('shop-frontend', 'app-web', 'dockerimage', OLD);
  const twice = run('pi', { provider: { applications: [application('shop-api', 'app-api', 'dockerimage', OLD, 'shop-backend'), application('shop-api', 'other-api', 'dockerimage', OLD, 'shop-backend'), web] } });
  await assert.rejects(twice.result, /2 Docker image applications on the Pi are named shop-api; nothing was released/);
  assert.deepEqual(twice.calls, []);

  const foreign = run('pi', { provider: { applications: [application('shop-api', 'app-api', 'dockerimage', OLD, 'someone-else'), web] } });
  await assert.rejects(foreign.result, /shop-api on the Pi runs ghcr.io\/f0rge\/someone-else, not ghcr.io\/f0rge\/shop-backend; nothing was released/);
  assert.deepEqual(foreign.calls, []);
});

test('rejects an unknown App and a short commit', async () => {
  await assert.rejects(deploy({ app: 'nope', commit: NEW, root: repo('pi'), env: {} }), /not a deployable App/);
  await assert.rejects(deploy({ app: 'shop', commit: 'abc123', root: repo('pi'), env: {} }), /full 40-character commit sha/);
});
