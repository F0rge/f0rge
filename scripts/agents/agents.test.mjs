import assert from 'node:assert/strict';
import { mkdtempSync, mkdirSync, readFileSync, writeFileSync, rmSync, readdirSync, symlinkSync, lstatSync, existsSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import test from 'node:test';
import { ROOT, MANIFEST, ROLE_IDS, loadManifest, validateManifest, globRegex, route, generate, adapterContents, checkAdapters, checkAdrReferences, checkLiveCallers, check, repositoryFiles } from './agents.mjs';

const manifest = loadManifest();
const fixtures = JSON.parse(readFileSync(new URL('./routing-fixtures.json', import.meta.url), 'utf8'));
function write(root, path, content) {
  mkdirSync(dirname(join(root, path)), { recursive: true });
  writeFileSync(join(root, path), content);
}
function fixture(t) {
  const root = mkdtempSync(join(tmpdir(), 'f0rge-agents-test-'));
  t.after(() => rmSync(root, { recursive: true, force: true }));
  for (const path of [MANIFEST, manifest.protocol, ...manifest.roles.map((role) => role.profile), ...readdirSync(join(ROOT, 'docs/adr')).filter((name) => name.endsWith('.md')).map((name) => `docs/adr/${name}`)]) {
    write(root, path, readFileSync(join(ROOT, path), 'utf8'));
  }
  return root;
}

test('ordered primary routing and independently accumulated reviewers', async (t) => {
  for (const item of fixtures) await t.test(item.path, () => {
    if (item.error) return assert.throws(() => route(manifest, item.path), new RegExp(item.error));
    const result = route(manifest, item.path);
    assert.equal(result.owner, item.owner);
    for (const reviewer of item.reviewers) assert.ok(result.reviewers.includes(reviewer), `Missing ${reviewer}`);
    assert.equal(result.reviewers.length, new Set(result.reviewers).size);
  });
});

test('every current tracked or non-ignored repository path has an explicit classification', () => {
  const paths = repositoryFiles();
  assert.ok(paths.length > 1000);
  for (const path of paths) assert.ok(ROLE_IDS.includes(route(manifest, path).owner), path);
});

test('wildcards respect segments and zero-directory **; invalid path syntax fails closed', () => {
  assert.ok(globRegex('**/AGENTS.md').test('AGENTS.md'));
  assert.ok(globRegex('**/AGENTS.md').test('apps/a/AGENTS.md'));
  assert.ok(!globRegex('apps/*/backend/**').test('apps/a/deeper/backend/foo.py'));
  assert.ok(globRegex('a/?.ts').test('a/x.ts'));
  assert.ok(!globRegex('a/?.ts').test('a/xx.ts'));
  for (const path of ['../AGENTS.md', '/tmp/AGENTS.md', 'a/../AGENTS.md', 'a\\AGENTS.md', 'a//b', 'a/./b']) assert.throws(() => route(manifest, path), /Invalid repository-relative/);
  for (const pattern of ['a/**b', 'a/{b,c}', '!a/b', 'a/[bc]']) assert.throws(() => globRegex(pattern));
  assert.equal(route(manifest, './AGENTS.md').path, 'AGENTS.md');
});

test('first matching owner never suppresses later or same-role independent reviewers', () => {
  const result = route(manifest, '.github/workflows/deploy.yml');
  assert.equal(result.owner, 'f0rge-delivery');
  assert.deepEqual(result.reviewers, ['f0rge-quality-testing', 'f0rge-devops', 'f0rge-delivery', 'f0rge-security']);
});

test('generation is deterministic, self-contained, and inherits native model/tools/permissions', (t) => {
  const root = fixture(t);
  assert.equal(generate(manifest, root), 8);
  assert.deepEqual(readdirSync(root).sort(), ['.codex', 'docs']);
  const first = adapterContents(manifest, root);
  generate(manifest, root);
  assert.deepEqual(adapterContents(manifest, root), first);
  assert.deepEqual(checkAdapters(manifest, root), []);
  for (const role of manifest.roles) {
    for (const [path, body] of first) {
      if (!path.includes(role.id)) continue;
      const protocol = readFileSync(join(root, manifest.protocol), 'utf8').trim();
      const profile = readFileSync(join(root, role.profile), 'utf8').trim();
      const decoded = body.slice(body.indexOf('developer_instructions = """\n') + 'developer_instructions = """\n'.length, -4).replaceAll('\\"', '"').replaceAll('\\\\', '\\');
      assert.ok(decoded.includes(protocol));
      assert.ok(decoded.includes(profile));
      assert.ok(!/^(?:model|tools|permission_mode|sandbox_mode)\s*[:=]/mu.test(body));
      assert.match(body, /name\s*[:=]/u);
      assert.match(body, /description\s*[:=]/u);
    }
  }
});

test('adapter escaping preserves quotes, backslashes and triple quotes', (t) => {
  const root = fixture(t);
  write(root, manifest.roles[0].profile, '# Backend\nQuotes: """; path: C:\\example\\file\n');
  const body = adapterContents(manifest, root).get('.codex/agents/f0rge-backend.toml');
  assert.ok(body.includes('Quotes: \\"\\"\\"; path: C:\\\\example\\\\file'));
});

test('missing, edited and extra owned adapters fail; other namespaces are untouched', (t) => {
  const root = fixture(t);
  generate(manifest, root);
  write(root, '.codex/agents/personal-helper.toml', 'other owner');
  assert.deepEqual(checkAdapters(manifest, root), []);
  rmSync(join(root, '.codex/agents/f0rge-data.toml'));
  write(root, '.codex/agents/f0rge-backend.toml', 'manual edit');
  write(root, '.codex/agents/f0rge-unexpected.toml', 'extra');
  const errors = checkAdapters(manifest, root);
  assert.ok(errors.some((error) => error.includes('Missing generated')));
  assert.ok(errors.some((error) => error.includes('adapter drift')));
  assert.ok(errors.some((error) => error.includes('Unexpected repository-owned')));
  generate(manifest, root);
  assert.equal(readFileSync(join(root, '.codex/agents/personal-helper.toml'), 'utf8'), 'other owner');
  assert.equal(readFileSync(join(root, '.codex/agents/f0rge-unexpected.toml'), 'utf8'), 'extra');
});

test('check detects drift without repairing files or writing new files', (t) => {
  const root = fixture(t);
  generate(manifest, root);
  const path = '.codex/agents/f0rge-backend.toml';
  write(root, path, 'intentional drift');
  const before = readdirSync(join(root, '.codex/agents')).map((name) => [name, readFileSync(join(root, '.codex/agents', name), 'utf8')]);
  assert.ok(check(manifest, root, []).some((error) => error.includes('adapter drift')));
  const after = readdirSync(join(root, '.codex/agents')).map((name) => [name, readFileSync(join(root, '.codex/agents', name), 'utf8')]);
  assert.deepEqual(after, before);
});

test('manifest rejects unknown/duplicate roles, invalid owner/reviewer and catch-all routing', (t) => {
  const root = fixture(t);
  const mutations = [
    (m) => { m.roles[0].id = 'f0rge-unknown'; },
    (m) => { m.roles[0] = m.roles[1]; },
    (m) => { m.roles[0].description = ''; },
    (m) => { m.roles[0].profile = '../secret.md'; },
    (m) => { m.primaryRules[0].owner = 'unknown'; },
    (m) => { m.primaryRules[0].patterns = ['**']; },
    (m) => { m.reviewerRules[0].reviewers = ['unknown']; },
    (m) => { m.adapters.push('unverified-harness'); },
    (m) => { m.adapters = []; },
    (m) => { m.adapters = ['unverified-harness']; },
    (m) => { m.adapters = ['codex', 'codex']; },
    (m) => { m.schemaVersion = 2; },
  ];
  for (const mutate of mutations) {
    const candidate = structuredClone(manifest); mutate(candidate);
    assert.throws(() => validateManifest(candidate, root));
  }
});

test('missing source/ADR file and unknown or misplaced ADR IDs fail', (t) => {
  const root = fixture(t);
  const path = manifest.roles[0].profile;
  write(root, path, '# Backend\nP-999\n[missing](docs/adr/missing.md)\n[wrong category](docs/adr/data.md#p-011)\n');
  const errors = checkAdrReferences([path], root);
  assert.ok(errors.some((error) => error.includes('unknown ADR ID P-999')));
  assert.ok(errors.some((error) => error.includes('missing ADR file')));
  assert.ok(errors.some((error) => error.includes('missing ADR heading')));
  rmSync(join(root, manifest.roles[0].adrFiles[0]));
  assert.throws(() => validateManifest(manifest, root), /ENOENT/);
});

test('active obsolete dispatch/model/global loader requirements fail; provenance paths survive', (t) => {
  const root = fixture(t);
  const path = 'AGENTS.md';
  for (const content of ['Delegate to `fastapi-backend`.', 'Use `devops` sub-agent.', 'model: pinned-model', 'model_provider = pinned-provider', 'Read ~/.codex/agents/backend.toml.', 'Must read ~/.codex/agent-memory/backend/MEMORY.md.', 'Before starting, read ~/.codex/memories_v2/summary.md.']) {
    write(root, path, content);
    assert.equal(checkLiveCallers(manifest, [path], root).length, 1, content);
  }
  write(root, path, 'Historical provenance: frontend-dev/dnd_kit_grid_drag_reorder.md.\nRead docs/agents/review-context/fastapi-backend-playbook.md.\nUse f0rge-devops and f0rge-backend.');
  assert.deepEqual(checkLiveCallers(manifest, [path], root), []);
});


test('extra canonical profiles fail instead of silently creating a ninth role', (t) => {
  const root = fixture(t);
  generate(manifest, root);
  write(root, 'docs/agents/profiles/generalist.md', '# Unapproved profile');
  assert.ok(checkAdapters(manifest, root).some((error) => error.includes('Unexpected canonical profile')));
});

test('live caller ADR links and non-ID headings are checked too', (t) => {
  const root = fixture(t);
  generate(manifest, root);
  write(root, 'AGENTS.md', '[missing](docs/adr/governance.md#no-such-heading)');
  assert.ok(check(manifest, root, ['AGENTS.md']).some((error) => error.includes('missing ADR heading')));
});


test('generation rejects a later symlinked output before changing any earlier output', async (t) => {
  for (const targetExists of [true, false]) await t.test(targetExists ? 'existing target' : 'dangling link', (t) => {
    const root = fixture(t);
    const outside = mkdtempSync(join(tmpdir(), 'f0rge-agents-external-'));
    t.after(() => rmSync(outside, { recursive: true, force: true }));
    const first = '.codex/agents/f0rge-backend.toml';
    const linked = '.codex/agents/f0rge-quality-testing.toml';
    const sentinel = join(outside, 'global-profile.md');
    write(root, first, 'earlier output must stay unchanged');
    mkdirSync(dirname(join(root, linked)), { recursive: true });
    if (targetExists) writeFileSync(sentinel, 'external sentinel');
    symlinkSync(sentinel, join(root, linked));

    assert.throws(() => generate(manifest, root), /symlink/iu);
    assert.equal(readFileSync(join(root, first), 'utf8'), 'earlier output must stay unchanged');
    assert.deepEqual(readdirSync(join(root, '.codex/agents')).sort(), ['f0rge-backend.toml', 'f0rge-quality-testing.toml']);
    assert.ok(lstatSync(join(root, linked)).isSymbolicLink());
    if (targetExists) assert.equal(readFileSync(sentinel, 'utf8'), 'external sentinel');
    else assert.equal(existsSync(sentinel), false);
  });
});

test('generation rejects symlinked output ancestors before writing adapters', async (t) => {
  for (const linked of ['.codex', '.codex/agents']) await t.test(linked, (t) => {
    const root = fixture(t);
    const outside = mkdtempSync(join(tmpdir(), 'f0rge-agents-external-'));
    t.after(() => rmSync(outside, { recursive: true, force: true }));
    const externalAdapters = linked === '.codex' ? join(outside, 'agents') : outside;
    mkdirSync(externalAdapters, { recursive: true });
    const sentinel = join(externalAdapters, 'f0rge-backend.toml');
    writeFileSync(sentinel, 'external sentinel');
    mkdirSync(dirname(join(root, linked)), { recursive: true });
    symlinkSync(outside, join(root, linked), 'dir');

    assert.throws(() => generate(manifest, root), /symlink/iu);
    assert.ok(lstatSync(join(root, linked)).isSymbolicLink());
    assert.equal(readFileSync(sentinel, 'utf8'), 'external sentinel');
    assert.deepEqual(readdirSync(externalAdapters), ['f0rge-backend.toml']);
  });
});
