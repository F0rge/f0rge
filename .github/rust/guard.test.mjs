import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {spawnSync} from 'node:child_process';
import test from 'node:test';
import {fileURLToPath} from 'node:url';
import {actions, inspectProjects, targetCommand, validate} from './guard.mjs';

const repository = fileURLToPath(new URL('../..', import.meta.url));
const node = process.execPath;
const nx = path.join(repository, 'node_modules/.bin/nx');
const env = {...process.env, NX_DAEMON: 'false', NX_ISOLATE_PLUGINS: 'false', NX_TASKS_RUNNER_DYNAMIC_OUTPUT: 'false'};
delete env.NX_WORKSPACE_ROOT;
const run = (cwd, command, args, options = {}) => spawnSync(command, args, {cwd, env, encoding: 'utf8', timeout: 90000, ...options});
const succeeds = result => assert.equal(result.status, 0, result.stdout + result.stderr);
function write(root, file, content) {
  const destination = path.join(root, file);
  fs.mkdirSync(path.dirname(destination), {recursive: true});
  fs.writeFileSync(destination, content);
}
function config(name, directory, dependencies = []) {
  return {name, tags: ['platform:rust', 'scope:fixture'], implicitDependencies: dependencies, targets: Object.fromEntries(actions.map(action => [action, {executor: 'nx:run-commands', cache: false, inputs: ['rust', '^rust'], outputs: [], options: {command: targetCommand(action, directory)}}]))};
}
function fixture(t) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'f0rge-rust-gates-'));
  t.after(() => fs.rmSync(root, {recursive: true, force: true}));
  write(root, 'package.json', JSON.stringify({name: 'rust-gates-fixture', private: true, devDependencies: {nx: JSON.parse(fs.readFileSync(path.join(repository, 'node_modules/nx/package.json'), 'utf8')).version}}));
  write(root, 'nx.json', JSON.stringify({defaultBase: 'main', namedInputs: {rust: JSON.parse(fs.readFileSync(path.join(repository, 'nx.json'), 'utf8')).namedInputs.rust}}));
  write(root, '.gitignore', 'node_modules/\n.nx/\ntarget/\n');
  fs.symlinkSync(path.join(repository, 'node_modules'), path.join(root, 'node_modules'), 'dir');
  for (const file of ['guard.mjs', 'run-target.mjs']) write(root, '.github/rust/' + file, fs.readFileSync(path.join(repository, '.github/rust', file)));
  write(root, 'rust-toolchain.toml', fs.readFileSync(path.join(repository, 'rust-toolchain.toml')));
  write(root, 'Cargo.toml', '[workspace]\nmembers = ["libs/shared", "apps/demo/backend"]\nresolver = "2"\n');
  write(root, 'libs/shared/Cargo.toml', '[package]\nname = "fixture-shared"\nversion = "0.1.0"\nedition = "2021"\n');
  write(root, 'libs/shared/src/lib.rs', 'pub fn value() -> u32 {\n    7\n}\n');
  write(root, 'libs/shared/project.json', JSON.stringify(config('fixture-shared', 'libs/shared')));
  write(root, 'apps/demo/backend/Cargo.toml', '[package]\nname = "fixture-app"\nversion = "0.1.0"\nedition = "2021"\n[dependencies]\nfixture-shared = { path = "../../../libs/shared" }\n');
  write(root, 'apps/demo/backend/src/lib.rs', 'pub fn value() -> u32 {\n    fixture_shared::value()\n}\n\n#[test]\nfn expected_value() {\n    assert_eq!(value(), 7);\n}\n');
  write(root, 'apps/demo/backend/project.json', JSON.stringify(config('fixture-app', 'apps/demo/backend', ['fixture-shared'])));
  succeeds(run(root, 'cargo', ['generate-lockfile', '--offline']));
  succeeds(run(root, 'git', ['init', '-q', '-b', 'main']));
  succeeds(run(root, 'git', ['add', '.']));
  succeeds(run(root, 'git', ['-c', 'user.name=Rust test fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-qm', 'synthetic fixture']));
  return root;
}
function updateProject(root, change) {
  const file = path.join(root, 'apps/demo/backend/project.json');
  const value = JSON.parse(fs.readFileSync(file, 'utf8'));
  change(value);
  fs.writeFileSync(file, JSON.stringify(value));
}
const nxRun = (root, action) => run(root, node, [nx, 'run', `fixture-app:${action}`, '--output-style=static']);
const affected = (root, file) => {
  const result = run(root, node, [nx, 'show', 'projects', '--affected', '--files=' + file, '--json']);
  succeeds(result);
  return JSON.parse(result.stdout);
};

test('static Cargo detection requires no Rust executable and accepts zero Rust projects', t => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'f0rge-rust-static-'));
  t.after(() => fs.rmSync(root, {recursive: true, force: true}));
  const result = run(root, node, [path.join(repository, '.github/rust/guard.mjs'), '--static'], {env: {...env, PATH: ''}});
  succeeds(result);
  assert.match(result.stdout, /0 projects/);
});

test('locked workspace and local path dependency registration are accepted', t => {
  const root = fixture(t);
  assert.equal(validate(root).length, 2);
  assert.equal(inspectProjects(root).size, 2);
});

test('missing registration, wrong platform, missing targets and no-op commands fail closed', t => {
  const root = fixture(t);
  const original = fs.readFileSync(path.join(root, 'apps/demo/backend/project.json'));
  fs.unlinkSync(path.join(root, 'apps/demo/backend/project.json'));
  assert.throws(() => inspectProjects(root), /requires sibling project.json/);
  fs.writeFileSync(path.join(root, 'apps/demo/backend/project.json'), original);
  updateProject(root, value => {value.tags = ['platform:ts', 'scope:fixture'];});
  assert.throws(() => inspectProjects(root), /platform:rust/);
  for (const action of actions) {
    fs.writeFileSync(path.join(root, 'apps/demo/backend/project.json'), original);
    updateProject(root, value => {delete value.targets[action];});
    assert.throws(() => inspectProjects(root), /fixed Rust runner/);
  }
  fs.writeFileSync(path.join(root, 'apps/demo/backend/project.json'), original);
  updateProject(root, value => {value.targets.build.options.command = 'echo skipped';});
  assert.throws(() => inspectProjects(root), /fixed Rust runner/);
  fs.writeFileSync(path.join(root, 'apps/demo/backend/project.json'), original);
  updateProject(root, value => {value.targets.build.cache = true;});
  assert.throws(() => inspectProjects(root), /uncached/);
});

test('missing local dependency edge and missing lock are rejected', t => {
  const root = fixture(t);
  updateProject(root, value => {value.implicitDependencies = [];});
  assert.throws(() => validate(root), /implicitDependencies: fixture-shared/);
  updateProject(root, value => {value.implicitDependencies = ['fixture-shared'];});
  const lock = fs.readFileSync(path.join(root, 'Cargo.lock'));
  fs.unlinkSync(path.join(root, 'Cargo.lock'));
  assert.throws(() => validate(root), /Cargo metadata failed|Cargo.lock/);
  assert.equal(fs.existsSync(path.join(root, 'Cargo.lock')), false);
  fs.writeFileSync(path.join(root, 'Cargo.lock'), lock);
});

test('valid actual Nx tasks run fmt, Clippy, tests and build through the runner', t => {
  const root = fixture(t);
  for (const action of actions) succeeds(nxRun(root, action));
});

for (const [action, broken, diagnostic] of [
  ['format-check', 'pub fn value()->u32{7}\n', /Diff in/],
  ['lint', 'pub fn compare(value: bool) -> bool {\n    value == true\n}\n', /bool_comparison/],
  ['test', '#[test]\nfn fails() {\n    assert_eq!(1, 2);\n}\n', /panicked|test result: FAILED/],
  ['build', 'pub fn value() -> u32 {\n    "not a number"\n}\n', /mismatched types|E0308/],
]) {
  test(`actual Nx ${action} cannot report success for a broken Rust project`, t => {
    const root = fixture(t);
    write(root, 'apps/demo/backend/src/lib.rs', broken);
    const result = nxRun(root, action);
    assert.notEqual(result.status, 0, result.stdout + result.stderr);
    assert.match(result.stdout + result.stderr, diagnostic);
  });
}

test('shared sources, lock/toolchain/config changes and tooling affect registered Rust projects', t => {
  const root = fixture(t);
  assert.deepEqual(affected(root, 'libs/shared/src/lib.rs').sort(), ['fixture-app', 'fixture-shared']);
  for (const file of ['Cargo.lock', 'Cargo.toml', 'rust-toolchain.toml', '.github/rust/run-target.mjs', '.cargo/config.toml']) {
    if (!fs.existsSync(path.join(root, file))) write(root, file, '# synthetic input\n');
    assert.deepEqual(affected(root, file).sort(), ['fixture-app', 'fixture-shared'], file);
  }
  assert.deepEqual(affected(root, 'apps/demo/backend/src/lib.rs'), ['fixture-app']);
});


test('root/input overrides and negated or wildcard dependency edges cannot hide Rust sources', t => {
  const root = fixture(t);
  const original = fs.readFileSync(path.join(root, 'apps/demo/backend/project.json'));
  for (const [change, message] of [
    [value => {value.root = 'libs/alias';}, /project root/],
    [value => {value.namedInputs = {rust: ['{projectRoot}/src/**/*']};}, /override namedInputs.rust/],
    [value => {value.implicitDependencies = ['fixture-shared', '!fixture-shared'];}, /unique exact project names/],
    [value => {value.implicitDependencies = ['fixture-*'];}, /unique exact project names/],
    [value => {value.implicitDependencies = ['fixture-shared', 'fixture-shared'];}, /unique exact project names/],
  ]) {
    fs.writeFileSync(path.join(root, 'apps/demo/backend/project.json'), original);
    updateProject(root, change);
    assert.throws(() => inspectProjects(root), message);
  }
  fs.writeFileSync(path.join(root, 'apps/demo/backend/project.json'), original);
  const nxConfig = JSON.parse(fs.readFileSync(path.join(root, 'nx.json'), 'utf8'));
  nxConfig.namedInputs.rust = nxConfig.namedInputs.rust.filter(input => input !== '{workspaceRoot}/**/Cargo.lock');
  write(root, 'nx.json', JSON.stringify(nxConfig));
  assert.throws(() => inspectProjects(root), /missing required Rust/);
});

test('stale or malformed Cargo locks fail actual Nx builds even when no-deps discovery succeeds', t => {
  const root = fixture(t);
  const manifest = path.join(root, 'apps/demo/backend/Cargo.toml');
  const original = fs.readFileSync(manifest, 'utf8');
  fs.writeFileSync(manifest, original.replace('version = "0.1.0"', 'version = "0.2.0"'));
  assert.equal(validate(root).length, 2);
  const stale = nxRun(root, 'build');
  assert.notEqual(stale.status, 0, stale.stdout + stale.stderr);
  assert.match(stale.stdout + stale.stderr, /lock file.*needs to be updated|lockfile.*needs to be updated|--locked/s);
  fs.writeFileSync(manifest, original);
  write(root, 'Cargo.lock', 'not a cargo lockfile');
  const malformed = nxRun(root, 'build');
  assert.notEqual(malformed.status, 0, malformed.stdout + malformed.stderr);
  assert.match(malformed.stdout + malformed.stderr, /failed to parse lock file|TOML parse error/);
});


test('standalone package roots use their own locked metadata and explicit local edges', t => {
  const root = fixture(t);
  fs.unlinkSync(path.join(root, 'Cargo.toml'));
  fs.unlinkSync(path.join(root, 'Cargo.lock'));
  for (const directory of ['libs/shared', 'apps/demo/backend']) succeeds(run(root, 'cargo', ['generate-lockfile', '--manifest-path', path.join(root, directory, 'Cargo.toml'), '--offline']));
  assert.equal(validate(root).length, 2);
});

test('declaring an Nx edge cannot authorize a shared Rust library to import an app', t => {
  const root = fixture(t);
  const appManifest = path.join(root, 'apps/demo/backend/Cargo.toml');
  fs.writeFileSync(appManifest, fs.readFileSync(appManifest, 'utf8').split('[dependencies]')[0]);
  write(root, 'apps/demo/backend/src/lib.rs', 'pub fn value() -> u32 { 7 }\n');
  updateProject(root, value => {value.implicitDependencies = [];});
  fs.appendFileSync(path.join(root, 'libs/shared/Cargo.toml'), '[dependencies]\nfixture-app = { path = "../../apps/demo/backend" }\n');
  const file = path.join(root, 'libs/shared/project.json');
  const config = JSON.parse(fs.readFileSync(file, 'utf8'));
  config.implicitDependencies = ['fixture-app'];
  fs.writeFileSync(file, JSON.stringify(config));
  succeeds(run(root, 'cargo', ['generate-lockfile', '--offline']));
  assert.throws(() => validate(root), /shared libraries must not depend on app crates/);
});

test('the existing registration shell catches Cargo and retains Node/Python checks', t => {
  const root = fixture(t);
  write(root, '.github/scripts/check-nx-projects.sh', fs.readFileSync(path.join(repository, '.github/scripts/check-nx-projects.sh')));
  succeeds(run(root, 'bash', ['.github/scripts/check-nx-projects.sh']));
  for (const manifest of ['package.json', 'pyproject.toml']) {
    const directory = path.join(root, 'apps/unregistered');
    write(root, `apps/unregistered/${manifest}`, manifest === 'package.json' ? '{}' : '[project]\nname="unregistered"\n');
    const result = run(root, 'bash', ['.github/scripts/check-nx-projects.sh']);
    assert.notEqual(result.status, 0);
    assert.match(result.stdout, /unregistered.*no project.json/);
    fs.rmSync(directory, {recursive: true});
  }
  fs.unlinkSync(path.join(root, 'apps/demo/backend/project.json'));
  const result = run(root, 'bash', ['.github/scripts/check-nx-projects.sh']);
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /Cargo.toml requires sibling project.json/);
});

test('nested virtual workspaces are rejected even if assigned a fake Nx package project', t => {
  const root = fixture(t);
  write(root, 'libs/nested/Cargo.toml', '[workspace]\nmembers=["child"]\nresolver="2"\n');
  write(root, 'libs/nested/project.json', JSON.stringify(config('nested-workspace', 'libs/nested')));
  write(root, 'libs/nested/child/Cargo.toml', '[package]\nname="nested-child"\nversion="0.1.0"\nedition="2021"\n');
  write(root, 'libs/nested/child/src/lib.rs', 'pub fn value() -> u32 { 7 }\n');
  write(root, 'libs/nested/child/project.json', JSON.stringify(config('nested-child', 'libs/nested/child')));
  succeeds(run(root, 'cargo', ['generate-lockfile', '--manifest-path', path.join(root, 'libs/nested/Cargo.toml'), '--offline']));
  assert.throws(() => validate(root), /Nested virtual Cargo workspaces are not supported/);
});
