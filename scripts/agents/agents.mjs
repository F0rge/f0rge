#!/usr/bin/env node
// Repository-owned routing and adapter generation, not a harness loader or permission boundary.
import { execFileSync } from 'node:child_process';
import { existsSync, lstatSync, mkdirSync, readFileSync, readdirSync, writeFileSync } from 'node:fs';
import { dirname, isAbsolute, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

export const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '../..');
export const MANIFEST = 'docs/agents/manifest.json';
export const ROLE_IDS = ['backend', 'frontend', 'data', 'security', 'delivery', 'devops', 'workflows', 'quality-testing'].map((id) => `f0rge-${id}`);
const CODEX_ADAPTER_DIR = '.codex/agents';

function requireValue(condition, message) {
  if (!condition) throw new Error(message);
}

export function repositoryPath(value) {
  requireValue(typeof value === 'string' && value.length > 0, 'Expected a nonempty repository-relative path');
  const path = value.startsWith('./') ? value.slice(2) : value;
  requireValue(!isAbsolute(path) && !path.includes('\\') && !/[\u0000-\u001f]/u.test(path)
    && path.split('/').every((part) => part && part !== '.' && part !== '..'), `Invalid repository-relative path: ${value}`);
  return path;
}

// Deliberately small glob language: * and ? within a segment, ** as a whole segment.
// No brace expansion, negation, regex, or OS-dependent path matching.
export function globRegex(pattern) {
  repositoryPath(pattern);
  requireValue(!/[\[\]{}!]/u.test(pattern), `Unsupported glob syntax: ${pattern}`);
  const parts = pattern.split('/');
  const expression = parts.map((part, index) => {
    if (part === '**') return index === parts.length - 1 ? '.*' : '(?:[^/]+/)*';
    requireValue(!part.includes('**'), `** must be a whole path segment: ${pattern}`);
    const escaped = [...part].map((character) => character === '*' ? '[^/]*' : character === '?' ? '[^/]' : character.replace(/[.*+?^${}()|[\]\\]/gu, '\\$&')).join('');
    return escaped + (index < parts.length - 1 ? '/' : '');
  }).join('');
  return new RegExp(`^${expression}$`, 'u');
}

function matches(path, patterns) {
  return patterns.some((pattern) => globRegex(pattern).test(path));
}

export function route(manifest, value) {
  const path = repositoryPath(value);
  const primary = manifest.primaryRules.find((rule) => matches(path, rule.patterns));
  requireValue(primary, `Unclassified path: ${path}. Add a reviewed primary rule to ${MANIFEST}.`);
  const reviewers = [...new Set(manifest.reviewerRules.filter((rule) => matches(path, rule.patterns)).flatMap((rule) => rule.reviewers))];
  // Keep the primary role in reviewers: a distinct instance must review its own domain.
  return { path, owner: primary.owner, reviewers, reason: primary.reason };
}

function read(root, path) {
  return readFileSync(resolve(root, repositoryPath(path)), 'utf8');
}

export function loadManifest(root = ROOT) {
  return JSON.parse(read(root, MANIFEST));
}

function validatePatterns(patterns, location) {
  requireValue(Array.isArray(patterns) && patterns.length > 0, `${location}: nonempty patterns required`);
  patterns.forEach(globRegex);
}

export function validateManifest(manifest, root = ROOT) {
  requireValue(manifest?.schemaVersion === 1, 'Unsupported manifest schemaVersion');
  requireValue(manifest.protocol === 'docs/agents/protocol.md', 'Unexpected canonical protocol path');
  requireValue(Array.isArray(manifest.adapters) && manifest.adapters.length === 1
    && manifest.adapters[0] === 'codex', 'The only supported adapter is codex');
  requireValue(Array.isArray(manifest.roles) && manifest.roles.length === 8, 'Exactly eight repository-owned roles required');
  requireValue([...manifest.roles.map((role) => role.id)].sort().join(',') === [...ROLE_IDS].sort().join(','), 'Invalid, missing, or duplicate role IDs');
  for (const role of manifest.roles) {
    requireValue(typeof role.description === 'string' && role.description.trim().length > 0 && !/[\u0000-\u001f]/u.test(role.description), `${role.id}: nonempty single-line description required`);
    requireValue(role.profile === `docs/agents/profiles/${role.id.slice('f0rge-'.length)}.md`, `${role.id}: unexpected canonical profile path`);
    requireValue(read(root, role.profile).trim().length > 0, `${role.id}: empty profile`);
    requireValue(Array.isArray(role.adrFiles) && role.adrFiles.length > 0, `${role.id}: adrFiles required`);
    for (const file of role.adrFiles) {
      requireValue(/^docs\/adr\/[a-z-]+\.md$/u.test(file), `Invalid ADR path: ${file}`);
      read(root, file);
    }
  }
  requireValue(read(root, manifest.protocol).trim().length > 0, 'Empty protocol');
  requireValue(Array.isArray(manifest.primaryRules) && manifest.primaryRules.length > 0, 'primaryRules required');
  for (const rule of manifest.primaryRules) {
    validatePatterns(rule.patterns, 'primaryRules');
    requireValue(!rule.patterns.includes('**') && !rule.patterns.includes('*'), 'Unscoped primary catch-all is forbidden');
    requireValue(ROLE_IDS.includes(rule.owner), `Unknown primary owner: ${rule.owner}`);
    requireValue(typeof rule.reason === 'string' && rule.reason.trim().length > 0, 'Primary rule reason required');
  }
  requireValue(Array.isArray(manifest.reviewerRules) && manifest.reviewerRules.length > 0, 'reviewerRules required');
  for (const rule of manifest.reviewerRules) {
    validatePatterns(rule.patterns, 'reviewerRules');
    requireValue(Array.isArray(rule.reviewers) && rule.reviewers.length > 0 && rule.reviewers.every((id) => ROLE_IDS.includes(id)), 'Unknown or missing mandatory reviewer');
  }
  validatePatterns(manifest.liveCallerPatterns, 'liveCallerPatterns');
  return manifest;
}

export function adapterContents(manifest, root = ROOT) {
  const generated = new Map();
  const protocol = read(root, manifest.protocol).trim();
  for (const role of manifest.roles) {
    const body = `Generated from ${manifest.protocol} and ${role.profile} through ${MANIFEST}. Edit those sources, then run npm run agents:generate.\n\n${protocol}\n\n${read(root, role.profile).trim()}\n`;
    const path = `${CODEX_ADAPTER_DIR}/${role.id}.toml`;
    // TOML multiline basic string: escape backslashes before quotes; preserve readable lines.
    const instructions = body.replaceAll('\\', '\\\\').replaceAll('"', '\\"');
    generated.set(path, `# Generated by scripts/agents/agents.mjs; do not edit.\nname = ${JSON.stringify(role.id)}\ndescription = ${JSON.stringify(role.description)}\ndeveloper_instructions = """\n${instructions}"""\n`);
  }
  return generated;
}

function preflightOutputs(paths, root) {
  // Inspect the selected repository root and every output component without following
  // links. Finish the whole preflight before mkdir/write so a later unsafe output
  // cannot leave earlier adapters partially regenerated. Concurrent path mutation
  // by another process is outside this local generator's guarantees.
  for (const path of paths) {
    const components = [resolve(root), ...repositoryPath(path).split('/')];
    let current = components[0];
    for (let index = 0; index < components.length; index += 1) {
      if (index > 0) current = resolve(current, components[index]);
      const status = lstatSync(current, { throwIfNoEntry: false });
      if (!status) continue;
      requireValue(!status.isSymbolicLink(), `Refusing generated output through symlink: ${current}`);
      const isOutput = index === components.length - 1;
      requireValue(isOutput ? status.isFile() : status.isDirectory(), `Invalid generated output ${isOutput ? 'file' : 'directory'}: ${current}`);
    }
  }
}

export function generate(manifest, root = ROOT) {
  validateManifest(manifest, root);
  const generated = adapterContents(manifest, root);
  preflightOutputs(generated.keys(), root);
  for (const [path, content] of generated) {
    mkdirSync(dirname(resolve(root, path)), { recursive: true });
    writeFileSync(resolve(root, path), content);
  }
  // Deliberately do not remove extra files, including other owners' profiles.
  return generated.size;
}

export function checkAdapters(manifest, root = ROOT) {
  const expected = adapterContents(manifest, root);
  const errors = [];
  for (const [path, content] of expected) {
    if (!existsSync(resolve(root, path))) errors.push(`Missing generated adapter: ${path}`);
    else if (read(root, path) !== content) errors.push(`Generated adapter drift: ${path}. Run npm run agents:generate.`);
  }
  if (existsSync(resolve(root, CODEX_ADAPTER_DIR))) {
    for (const name of readdirSync(resolve(root, CODEX_ADAPTER_DIR))) {
      // Check only our namespace; built-ins and user/other repository profiles are independent.
      const path = `${CODEX_ADAPTER_DIR}/${name}`;
      if (name.startsWith('f0rge-') && !expected.has(path)) errors.push(`Unexpected repository-owned adapter: ${path}`);
    }
  }
  const profiles = new Set(manifest.roles.map((role) => role.profile));
  for (const name of readdirSync(resolve(root, 'docs/agents/profiles'))) {
    if (name.endsWith('.md') && !profiles.has(`docs/agents/profiles/${name}`)) errors.push(`Unexpected canonical profile: docs/agents/profiles/${name}`);
  }
  return errors;
}

export function repositoryFiles(root = ROOT) {
  return [...new Set(execFileSync('git', ['ls-files', '-z', '--cached', '--others', '--exclude-standard'], { cwd: root, maxBuffer: 16 * 1024 * 1024 }).toString().split('\0').filter(Boolean))]
    .filter((path) => existsSync(resolve(root, path))).sort();
}

export function checkAdrReferences(paths, root = ROOT) {
  const records = new Map();
  const adrs = readdirSync(resolve(root, 'docs/adr')).filter((name) => name.endsWith('.md'));
  for (const name of adrs) {
    const file = `docs/adr/${name}`;
    for (const match of read(root, file).matchAll(/^## ([PC]-\d{3})\s*$/gmu)) records.set(match[1], file);
  }
  const errors = [];
  for (const path of paths) {
    const content = read(root, path);
    for (const match of content.matchAll(/\b[PC]-\d{3}\b/gu)) {
      if (!records.has(match[0])) errors.push(`${path}: unknown ADR ID ${match[0]}`);
    }
    for (const match of content.matchAll(/docs\/adr\/([a-z-]+\.md)(?:#([a-z0-9-]+))?/gu)) {
      const file = `docs/adr/${match[1]}`;
      if (!existsSync(resolve(root, file))) errors.push(`${path}: missing ADR file ${file}`);
      else if (match[2]) {
        const headings = [...read(root, file).matchAll(/^#+ (.+)$/gmu)].map((heading) => heading[1].toLowerCase().replace(/[^\p{L}\p{N}_ -]/gu, '').replaceAll(' ', '-'));
        if (!headings.includes(match[2])) errors.push(`${path}: missing ADR heading ${file}#${match[2]}`);
      }
    }
  }
  return [...new Set(errors)];
}

export function checkLiveCallers(manifest, paths, root = ROOT) {
  const errors = [];
  for (const path of paths.filter((file) => matches(file, manifest.liveCallerPatterns))) {
    read(root, path).split('\n').forEach((line, index) => {
      // Paths to old playbooks and explicitly historical memory citations remain useful provenance.
      const staleRole = /(?<![\w/-])(?:fastapi-backend|frontend-dev|data-engineer|data-scientist|qa-engineer)(?![\w/-])/u.test(line) || /`devops`/u.test(line);
      const hardModel = /(?:^|\s)(?:model|model_provider)\s*[:=]\s*\S/u.test(line);
      const globalLoader = /~\/\.[\w-]+\/agents\//u.test(line);
      const requiredMemory = /(?:must|required|before starting|read|write back).*~\/\.[\w-]+\/(?:agent-memory|memories(?:_v\d+)?)\//iu.test(line) && !/historical|optional|when available/iu.test(line);
      if (staleRole || hardModel || globalLoader || requiredMemory) errors.push(`${path}:${index + 1}: stale role, model, or global loader requirement`);
    });
  }
  return errors;
}

export function check(manifest, root = ROOT, paths = repositoryFiles(root)) {
  validateManifest(manifest, root);
  const instructionPaths = [...new Set([manifest.protocol, ...manifest.roles.map((role) => role.profile), ...paths.filter((path) => matches(path, manifest.liveCallerPatterns))])];
  const errors = [...checkAdapters(manifest, root), ...checkAdrReferences(instructionPaths, root), ...checkLiveCallers(manifest, paths, root)];
  for (const path of paths) {
    try { route(manifest, path); } catch (error) { errors.push(error.message); }
  }
  return errors;
}

function main() {
  const [command, ...paths] = process.argv.slice(2);
  const manifest = loadManifest();
  if (command === 'generate' && paths.length === 0) {
    console.log(`Generated ${generate(manifest)} Codex adapters. Run npm run agents:check.`);
  } else if (command === 'check' && paths.length === 0) {
    const files = repositoryFiles();
    const errors = check(manifest, ROOT, files);
    if (errors.length) throw new Error(errors.join('\n'));
    console.log(`Agent checks passed: ${manifest.roles.length} repository roles, ${adapterContents(manifest).size} adapters, ${files.length} classified files. Native discovery and policy compliance require separate verification.`);
  } else if (command === 'route' && paths.length > 0) {
    validateManifest(manifest);
    console.log(JSON.stringify(paths.map((path) => route(manifest, path)), null, 2));
  } else throw new Error('Usage: node scripts/agents/agents.mjs generate|check|route <repo-relative-path...>');
}

if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) {
  try { main(); } catch (error) { console.error(error.message); process.exitCode = 1; }
}
