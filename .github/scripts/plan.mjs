#!/usr/bin/env node
// What CI has to do for this change: which language jobs run, and which Apps get
// their images built (and, on main, released). Prints one `key=value` line per job output.
import { execFileSync } from 'node:child_process';
import { pathToFileURL } from 'node:url';
import { listApps } from '../deploy/deployables.mjs';

// affected: Nx project names. graph: the `graph` of `nx graph --print`. apps: listApps().
// An App is affected when any of its deployable Projects is; its job then covers all of them.
export function plan(affected, graph, apps) {
  const language = (platform) => affected.some((name) => graph.nodes[name]?.data.tags?.includes(`platform:${platform}`));
  return {
    py: language('py'),
    ts: language('ts'),
    rust: language('rust'),
    apps: apps
      .filter(({ projects }) => projects.some(({ name }) => affected.includes(name)))
      .map(({ app, host, projects }) => ({ app, host, projects: projects.map(({ name }) => name).join(',') })),
  };
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  // Nx reads the comparison range from NX_BASE / NX_HEAD (set by nrwl/nx-set-shas).
  const nx = (...args) => JSON.parse(execFileSync('npx', ['nx', ...args], { encoding: 'utf8', maxBuffer: 2 ** 28 }));
  const result = plan(nx('show', 'projects', '--affected', '--json'), nx('graph', '--print').graph, listApps());
  for (const [key, value] of Object.entries(result)) console.log(`${key}=${JSON.stringify(value)}`);
}
