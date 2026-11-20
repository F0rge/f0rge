import assert from 'node:assert/strict';
import { mkdirSync, mkdtempSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { test } from 'node:test';
import { listApps } from './deployables.mjs';

function repo(projects) {
  const root = mkdtempSync(join(tmpdir(), 'deployables-'));
  for (const [dir, json] of Object.entries(projects)) {
    mkdirSync(join(root, dir), { recursive: true });
    writeFileSync(join(root, dir, 'project.json'), JSON.stringify(json));
  }
  return root;
}
const deploy = (host, ...services) => ({ deploy: { host, services } });

test('groups deployable Projects by App, sorted, and ignores the rest', () => {
  const root = repo({
    'apps/zed/web': { name: 'zed-web', tags: ['platform:ts', 'scope:zed'], metadata: deploy('pi', { name: 'zed-web', port: 3000 }) },
    'apps/alpha/frontend': { name: 'alpha-frontend', tags: ['scope:alpha'], metadata: deploy('railway', { name: 'alpha-frontend', healthcheckPath: '/healthz' }) },
    'apps/alpha/backend': {
      name: 'alpha-backend',
      tags: ['platform:py', 'scope:alpha'],
      metadata: deploy('railway', { name: 'alpha-api', preDeployCommand: 'migrate' }, { name: 'alpha-worker' }),
    },
    'libs/ui': { name: 'ui', tags: ['scope:shared'] },
    'node_modules/pkg': { name: 'ignored', metadata: deploy('pi', { name: 'ignored' }) },
    'apps/alpha/frontend/dist': { name: 'built-copy', metadata: deploy('pi', { name: 'built-copy' }) },
  });
  assert.deepEqual(listApps(root), [
    {
      app: 'alpha',
      host: 'railway',
      projects: [
        {
          name: 'alpha-backend',
          root: 'apps/alpha/backend',
          image: 'ghcr.io/f0rge/alpha-backend',
          services: [{ name: 'alpha-api', preDeployCommand: 'migrate' }, { name: 'alpha-worker' }],
        },
        {
          name: 'alpha-frontend',
          root: 'apps/alpha/frontend',
          image: 'ghcr.io/f0rge/alpha-frontend',
          services: [{ name: 'alpha-frontend', healthcheckPath: '/healthz' }],
        },
      ],
    },
    {
      app: 'zed',
      host: 'pi',
      projects: [{ name: 'zed-web', root: 'apps/zed/web', image: 'ghcr.io/f0rge/zed-web', services: [{ name: 'zed-web', port: 3000 }] }],
    },
  ]);
});

test('rejects an App that mixes hosts', () => {
  const root = repo({
    a: { name: 'a', tags: ['scope:mix'], metadata: deploy('railway', { name: 'a' }) },
    b: { name: 'b', tags: ['scope:mix'], metadata: deploy('pi', { name: 'b' }) },
  });
  assert.throws(() => listApps(root), /mixes hosts/);
});

test('rejects a deployable Project without a scope tag, an unknown host, or a nameless service', () => {
  assert.throws(() => listApps(repo({ a: { name: 'a', tags: ['platform:ts'], metadata: deploy('pi', { name: 'a' }) } })), /scope:<app> tag/);
  assert.throws(() => listApps(repo({ a: { name: 'a', tags: ['scope:a'], metadata: deploy('fly', { name: 'a' }) } })), /railway or pi/);
  assert.throws(() => listApps(repo({ a: { name: 'a', tags: ['scope:a'], metadata: deploy('pi', {}) } })), /each with a name/);
});
