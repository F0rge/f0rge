// Lists every App that can be released: the Projects whose project.json carries
// metadata.deploy, grouped by their scope:<app> tag. No Nx, no dependencies.
import { readdirSync, readFileSync } from 'node:fs';
import { dirname, join, relative } from 'node:path';
import { pathToFileURL } from 'node:url';

const SKIP = new Set(['node_modules', '.nx', 'dist', 'target', '.git', '.venv', '.claude']);
const HOSTS = ['railway', 'pi'];

function* projectFiles(dir) {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    if (entry.isDirectory()) {
      if (!SKIP.has(entry.name)) yield* projectFiles(join(dir, entry.name));
    } else if (entry.name === 'project.json') yield join(dir, entry.name);
  }
}

// → [{ app, host, projects: [{ name, root, image, services: [...] }] }], sorted by app
export function listApps(root = process.cwd()) {
  const apps = new Map();
  for (const file of projectFiles(root)) {
    const { name, tags = [], metadata } = JSON.parse(readFileSync(file, 'utf8'));
    const deploy = metadata?.deploy;
    if (!deploy) continue;
    const app = tags.find((tag) => tag.startsWith('scope:'))?.slice('scope:'.length);
    if (!app) throw new Error(`${name}: a deployable Project needs a scope:<app> tag`);
    if (!HOSTS.includes(deploy.host)) throw new Error(`${name}: deploy.host must be railway or pi`);
    if (!deploy.services?.length || deploy.services.some((service) => !service.name))
      throw new Error(`${name}: deploy.services needs at least one service, each with a name`);
    const entry = apps.get(app) ?? { app, host: deploy.host, projects: [] };
    if (entry.host !== deploy.host) throw new Error(`App ${app} mixes hosts (${entry.host} and ${deploy.host})`);
    entry.projects.push({
      name,
      root: relative(root, dirname(file)),
      image: `ghcr.io/f0rge/${name}`,
      services: deploy.services,
    });
    apps.set(app, entry);
  }
  for (const entry of apps.values()) entry.projects.sort((a, b) => a.name.localeCompare(b.name));
  return [...apps.values()].sort((a, b) => a.app.localeCompare(b.app));
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href)
  console.log(JSON.stringify(listApps(), null, 2));
