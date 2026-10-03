#!/usr/bin/env node
'use strict';

const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const { spawnSync } = require('node:child_process');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

const root = path.resolve(__dirname, '../..');
const expectedName = 'braces';
const expectedVersion = '3.0.4-f0rge.1';
const expectedTarball = 'file:vendor/braces/braces-3.0.4-f0rge.1.tgz';
const vendorDir = path.join(root, 'vendor', 'braces');
const packageJsonPath = path.join(root, 'package.json');
const lockPath = path.join(root, 'package-lock.json');

function readJson(filePath) {
  return JSON.parse(fs.readFileSync(filePath, 'utf8'));
}

function packageDirectories(nodeModulesPath) {
  const found = [];
  const visitedModules = new Set();

  const isDirectory = (candidate) => {
    try {
      return fs.statSync(candidate).isDirectory();
    } catch {
      return false;
    }
  };

  const visitPackage = (packagePath, name) => {
    if (name === expectedName && isDirectory(packagePath)) {
      found.push(path.resolve(packagePath));
    }

    const nestedModules = path.join(packagePath, 'node_modules');
    if (isDirectory(nestedModules)) visitModules(nestedModules);
  };

  const visitModules = (modulesPath) => {
    if (!isDirectory(modulesPath)) return;
    let realPath;
    try {
      realPath = fs.realpathSync(modulesPath);
    } catch {
      return;
    }
    if (visitedModules.has(realPath)) return;
    visitedModules.add(realPath);

    for (const entry of fs.readdirSync(modulesPath, { withFileTypes: true })) {
      if (entry.name === '.bin') continue;
      const entryPath = path.join(modulesPath, entry.name);
      if (entry.name.startsWith('@') && isDirectory(entryPath)) {
        for (const scopedEntry of fs.readdirSync(entryPath, { withFileTypes: true })) {
          visitPackage(path.join(entryPath, scopedEntry.name), scopedEntry.name);
        }
      } else {
        visitPackage(entryPath, entry.name);
      }
    }
  };

  visitModules(nodeModulesPath);
  return [...new Set(found)];
}

function sourceFiles(packagePath) {
  const files = [];
  const walk = (relativePath) => {
    const absolutePath = path.join(packagePath, relativePath);
    if (!fs.existsSync(absolutePath)) return;
    const stat = fs.statSync(absolutePath);
    if (stat.isDirectory()) {
      for (const entry of fs.readdirSync(absolutePath).sort()) {
        walk(path.join(relativePath, entry));
      }
    } else if (relativePath === 'index.js' || relativePath.startsWith(`lib${path.sep}`) && relativePath.endsWith('.js')) {
      files.push(relativePath);
    }
  };
  walk('index.js');
  walk('lib');
  return files.sort();
}

function digest(filePath) {
  return crypto.createHash('sha256').update(fs.readFileSync(filePath)).digest('hex');
}

function localForkTarball(specifier) {
  return specifier === expectedTarball;
}

function verifyProvenance() {
  assert.ok(fs.existsSync(packageJsonPath), 'root package.json is missing');
  assert.ok(fs.existsSync(lockPath), 'package-lock.json is missing; refusing to skip dependency provenance');
  assert.ok(fs.existsSync(path.join(vendorDir, 'package.json')), 'vendored braces package is missing');

  const rootPackage = readJson(packageJsonPath);
  const vendorPackage = readJson(path.join(vendorDir, 'package.json'));
  const lock = readJson(lockPath);
  assert.equal(vendorPackage.name, expectedName, 'vendor package must keep upstream name `braces`');
  assert.equal(vendorPackage.version, expectedVersion, 'vendored braces version changed unexpectedly');

  const directSpecifier = rootPackage.dependencies?.braces ?? rootPackage.devDependencies?.braces;
  assert.ok(localForkTarball(directSpecifier), 'root must depend on the checked-in local braces tarball');
  assert.equal(rootPackage.overrides?.braces, '$braces', 'root npm override must pin every braces dependency to the local direct dependency');
  const tarballPath = path.resolve(root, directSpecifier.slice('file:'.length));
  assert.ok(fs.statSync(tarballPath).isFile(), 'local braces tarball is missing; run the dependency install before this check');

  const lockEntries = Object.entries(lock.packages || {}).filter(([packagePath]) =>
    packagePath === 'node_modules/braces' || packagePath.endsWith('/node_modules/braces'));
  assert.ok(lockEntries.length > 0, 'package-lock.json has no installed braces entries');
  for (const [packagePath, entry] of lockEntries) {
    assert.equal(entry.version, expectedVersion, `${packagePath} is not pinned to ${expectedVersion}`);
    assert.ok(localForkTarball(entry.resolved), `${packagePath} is not resolved from the checked-in braces tarball`);
    assert.equal(path.resolve(root, entry.resolved.slice('file:'.length)), tarballPath, `${packagePath} resolves to a different braces artifact`);
  }

  const installed = packageDirectories(path.join(root, 'node_modules'));
  assert.ok(installed.length > 0, 'no installed braces package was found; refusing to report a vacuous pass');
  assert.ok(installed.some((packagePath) => fs.realpathSync(packagePath) === fs.realpathSync(require.resolve('braces').replace(/[\\/]index\.js$/, ''))),
    'the root `require("braces")` does not resolve to a discovered installed copy');

  const expectedFiles = sourceFiles(vendorDir);
  assert.ok(expectedFiles.includes('index.js') && expectedFiles.some((file) => file.startsWith(`lib${path.sep}`)),
    'vendored braces source files are missing');
  for (const packagePath of installed) {
    const metadata = readJson(path.join(packagePath, 'package.json'));
    assert.equal(metadata.name, expectedName, `${packagePath} changed the public package name`);
    assert.equal(metadata.version, expectedVersion, `${packagePath} is not the patched version`);
    const installedFiles = sourceFiles(packagePath);
    assert.deepEqual(installedFiles, expectedFiles, `${packagePath} has a different source-file set than the local fork`);
    for (const file of expectedFiles) {
      assert.equal(digest(path.join(packagePath, file)), digest(path.join(vendorDir, file)), `${packagePath}/${file} differs from the vendored patch`);
    }
    const relativePath = path.relative(root, packagePath).split(path.sep).join('/');
    const lockEntry = lock.packages[relativePath];
    assert.ok(lockEntry, `${relativePath} is installed but has no matching lockfile entry`);
    assert.ok(localForkTarball(lockEntry.resolved), `${relativePath} is installed from an unverified source`);
  }

  return installed;
}

function verifyPublicBehavior(braces) {
  for (const pattern of ['{{a}}', '{a,{b}}', '{{x}y}', '{a,{b,{c}}', '{}{a}', '{1..8}']) {
    assert.equal(
      braces.stringify(braces.parse(pattern), { escapeInvalid: true }),
      pattern,
      `stringify escapeInvalid changed the published #72 behavior for ${pattern}`,
    );
  }

  assert.equal(braces.compile('{a,b', { escapeInvalid: true }), '\\{a,b');
  assert.deepEqual(braces.expand('{a,{b,c}}'), ['a', 'b', 'c']);
  assert.deepEqual(braces(['{a,b}', '{c,d}'], { expand: true, noempty: true }), ['a', 'b', 'c', 'd']);
  assert.deepEqual(braces('{a,a,b}', { expand: true, nodupes: true }), ['a', 'b']);
  assert.deepEqual(braces.expand('{1..3}', { rangeLimit: 3 }), ['1', '2', '3']);
  assert.throws(() => braces.expand('{1..3}', { rangeLimit: 2 }), RangeError);

  const maximumLegalPattern = '{'.repeat(100) + 'x' + '}'.repeat(100);
  const maximumLegalAst = braces.parse(maximumLegalPattern);
  assert.equal(braces.stringify(maximumLegalAst), maximumLegalPattern, 'the documented depth boundary must remain accepted');
  assert.doesNotThrow(() => braces.compile(maximumLegalAst));
  assert.doesNotThrow(() => braces.expand(maximumLegalAst));
  assert.throws(() => braces.parse('{'.repeat(101) + 'x' + '}'.repeat(101)), SyntaxError);
}

function runBoundedProbe(packagePath) {
  const entry = path.join(packagePath, 'index.js');
  const source = `
    const assert = require('node:assert/strict');
    const braces = require(${JSON.stringify(entry)});
    const hostile = '{'.repeat(3500) + 'a,b' + '}'.repeat(3500);
    for (const method of ['parse', 'compile', 'expand', 'stringify']) {
      assert.throws(() => braces[method](hostile), SyntaxError, method + ' must reject over-depth input with SyntaxError');
    }
    assert.throws(() => braces.parse(hostile, { maxDepth: 1000000 }), SyntaxError, 'maxDepth cannot disable the hard cap');

    const makeDeepAst = (depth) => {
      const root = { type: 'root', nodes: [] };
      let node = root;
      for (let index = 0; index < depth; index += 1) {
        const child = { type: 'brace', nodes: [], parent: node };
        node.nodes.push(child);
        node = child;
      }
      node.nodes.push({ type: 'text', value: 'x', parent: node });
      return root;
    };
    const deepAst = makeDeepAst(2000);
    for (const method of ['compile', 'expand', 'stringify']) {
      assert.throws(() => braces[method](deepAst), SyntaxError, method + ' must bound direct AST depth');
    }

    const makeDeepDagAst = (depth) => {
      const root = { type: 'root', nodes: [] };
      let previous = { type: 'text', value: 'x' };
      for (let index = 0; index < depth; index += 1) {
        const parent = { type: 'brace', nodes: [previous] };
        root.nodes.push(parent);
        previous = parent;
      }
      return root;
    };
    const deepDagAst = makeDeepDagAst(200);
    for (const method of ['compile', 'expand', 'stringify']) {
      assert.throws(() => braces[method](deepDagAst), SyntaxError, method + ' must enforce depth across shared DAG nodes');
    }

    const sharedAst = { type: 'root', nodes: [] };
    const sharedLeaf = { type: 'text', value: 'x', parent: sharedAst };
    sharedAst.nodes.push(sharedLeaf, sharedLeaf);
    assert.equal(braces.compile(sharedAst), 'xx', 'valid shared AST nodes must remain supported');
    assert.equal(braces.stringify(sharedAst), 'xx', 'valid shared AST nodes must remain supported');
    assert.deepEqual(braces.expand(sharedAst), ['xx'], 'valid shared AST nodes must remain supported');

    const cyclicAst = { type: 'root', nodes: [] };
    cyclicAst.nodes.push(cyclicAst);
    for (const method of ['compile', 'expand', 'stringify']) {
      assert.throws(() => braces[method](cyclicAst), SyntaxError, method + ' must reject cyclic ASTs');
    }
    process.stdout.write('bounded hostile-input probes passed');
  `;
  const result = spawnSync(process.execPath, ['-e', source], {
    cwd: root,
    encoding: 'utf8',
    timeout: 10000,
    maxBuffer: 1024 * 1024,
  });
  if (result.error) throw new Error(`bounded braces probe failed or timed out: ${result.error.message}`);
  assert.equal(result.status, 0, `bounded braces probe failed: ${(result.stderr || result.stdout).trim()}`);
  assert.match(result.stdout, /bounded hostile-input probes passed/);
}

async function verifyGlobConsumers(installed) {
  const micromatchPath = require.resolve('micromatch');
  const fastGlobPath = require.resolve('fast-glob');
  const micromatchBracesPath = require.resolve('braces', { paths: [path.dirname(micromatchPath)] });
  const fastGlobMicromatchPath = require.resolve('micromatch', { paths: [path.dirname(fastGlobPath)] });
  const fastGlobBracesPath = require.resolve('braces', { paths: [path.dirname(fastGlobMicromatchPath)] });
  const installedEntries = new Set(installed.map((packagePath) => fs.realpathSync(path.join(packagePath, 'index.js'))));
  assert.ok(installedEntries.has(fs.realpathSync(micromatchBracesPath)), 'micromatch resolves an unpatched braces copy');
  assert.ok(installedEntries.has(fs.realpathSync(fastGlobBracesPath)), 'fast-glob resolves an unpatched braces copy');

  const micromatch = require(micromatchPath);
  assert.deepEqual(micromatch(['pkg/a.js', 'pkg/b.js', 'pkg/c.txt'], 'pkg/{a,b}.js'), ['pkg/a.js', 'pkg/b.js']);

  const fastGlob = require(fastGlobPath);
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'braces-security-'));
  try {
    fs.mkdirSync(path.join(directory, 'pkg'));
    for (const filename of ['a.js', 'b.js', 'c.txt']) {
      fs.writeFileSync(path.join(directory, 'pkg', filename), 'fixture');
    }
    const matches = await fastGlob('pkg/{a,b}.js', { cwd: directory, onlyFiles: true });
    assert.deepEqual(matches.sort(), ['pkg/a.js', 'pkg/b.js']);
  } finally {
    fs.rmSync(directory, { recursive: true, force: true });
  }
}

async function main() {
  const installed = verifyProvenance();
  const braces = require(require.resolve('braces'));
  verifyPublicBehavior(braces);
  for (const packagePath of installed) runBoundedProbe(packagePath);
  await verifyGlobConsumers(installed);
  console.log(`braces security regression check passed (${installed.length} installed patched copy/copies)`);
}

main().catch((error) => {
  console.error(`braces security regression check failed: ${error.stack || error.message}`);
  process.exitCode = 1;
});
