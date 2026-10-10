#!/usr/bin/env node
'use strict';

// Exercise the fixed public packages and the real Medusa consumer after npm ci.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawnSync } = require('node:child_process');
const root = path.resolve(__dirname, '../..');
const lock = JSON.parse(fs.readFileSync(path.join(root, 'package-lock.json'), 'utf8'));
const expected = {
  '@graphql-tools/utils': '12.0.3',
  'proxy-addr': '2.0.8',
  sharp: '0.35.5',
  'source-map-js': '1.2.2',
};

function installedCopies(name, version) {
  const entries = Object.entries(lock.packages).filter(([p]) =>
    p === `node_modules/${name}` || p.endsWith(`/node_modules/${name}`));
  assert.ok(entries.length, `lockfile has no ${name} copies`);
  const installed = [];
  for (const [relative, entry] of entries) {
    assert.equal(entry.version, version, `${relative} must use the fixed version`);
    assert.ok(entry.resolved.startsWith(`https://registry.npmjs.org/${name}/-/`),
      `${relative} must resolve to the official npm release`);
    assert.ok(entry.integrity?.startsWith('sha512-'), `${relative} must retain integrity`);
    const directory = path.join(root, relative);
    assert.ok(fs.existsSync(directory), `${relative} is missing; run the full npm ci first`);
    const metadata = JSON.parse(fs.readFileSync(path.join(directory, 'package.json'), 'utf8'));
    assert.equal(metadata.name, name);
    assert.equal(metadata.version, version, `${relative} installed version differs from lock`);
    installed.push(directory);
  }
  assert.ok(installed.length, `${name} is not installed; run npm ci first`);
  return installed;
}

function boundedSourceMapProbe(directory) {
  const result = spawnSync(process.execPath, ['-e', `
    const assert = require('node:assert/strict');
    const {SourceMapConsumer, SourceNode} = require(${JSON.stringify(directory)});
    const basic = {version:3, sources:['input.js'], names:[], mappings:'AAAA', sourcesContent:['x']};
    for (const line of [1e9, Infinity, NaN, -1, 0.5]) {
      assert.throws(() => {
        const consumer = new SourceMapConsumer({version:3, sections:[{offset:{line,column:0},map:basic}]});
        SourceNode.fromStringWithSourceMap('x', consumer);
      }, Error);
    }
    const consumer = new SourceMapConsumer({version:3, sections:[{offset:{line:1,column:0},map:basic}]});
    const mappings = [];
    consumer.eachMapping(mapping => mappings.push(mapping));
    assert.equal(mappings[0].source, 'input.js');
    assert.equal(mappings[0].generatedLine, 2);
    assert.equal(SourceNode.fromStringWithSourceMap('x', new SourceMapConsumer(basic)).toString(), 'x');
  `], {encoding: 'utf8', timeout: 5000, maxBuffer: 1024 * 1024});
  assert.ifError(result.error);
  assert.equal(result.status, 0, result.stderr || result.stdout);
}

async function main() {
  for (const [name, version] of Object.entries(expected)) {
    for (const directory of installedCopies(name, version)) {
      if (name === '@graphql-tools/utils') {
        const utils = require(directory);
        const call = Function.prototype.call;
        const hostile = JSON.parse('{"constructor":{"__proto__":{"call":"polluted"}},"__proto__":{"ciPolluted":true},"prototype":{"ciPolluted":true}}');
        utils.mergeDeep([{}, hostile]);
        assert.equal(Function.prototype.call, call);
        assert.equal(Object.prototype.ciPolluted, undefined);
        assert.deepEqual(utils.mergeDeep([{a:{left:1}},{a:{right:2}}]), {a:{left:1,right:2}});
        for (const segment of ['__proto__', 'constructor', 'prototype', ['__proto__']]) {
          utils.mergeIncrementalResult({executionResult:{data:{}},incrementalResult:{path:[segment],data:{ciPolluted:true}}});
          assert.equal(Object.prototype.ciPolluted, undefined);
          assert.equal(Function.prototype.call, call);
        }
      } else if (name === 'proxy-addr') {
        const proxy = require(directory);
        const request = {socket:{remoteAddress:'198.51.100.4'},headers:{'x-forwarded-for':'203.0.113.9'}};
        for (const subnet of ['::ffff:10.0.0.0/8', '::/1']) {
          assert.equal(proxy(request, proxy.compile(subnet)), '198.51.100.4');
        }
        assert.equal(proxy({...request,socket:{remoteAddress:'10.1.2.3'}}, proxy.compile('10.0.0.0/8')), '203.0.113.9');
      } else if (name === 'source-map-js') {
        boundedSourceMapProbe(directory);
      } else if (name === 'sharp') {
        const sharp = require(directory);
        const image = await sharp(Buffer.from('<svg xmlns="http://www.w3.org/2000/svg" width="4" height="4"><rect width="4" height="4" fill="red"/></svg>')).resize(2,2).png().toBuffer();
        const metadata = await sharp(image).metadata();
        assert.equal(metadata.width, 2);
        assert.equal(metadata.height, 2);
      }
    }
  }

  // Medusa 2.21.1 still uses Codegen 4 with utils ^10; verify its actual API seam.
  const medusaUtils = require('@medusajs/utils');
  const { buildSchema } = require('graphql');
  const { makeExecutableSchema } = require('@graphql-tools/schema');
  const { mergeTypeDefs } = require('@graphql-tools/merge');
  const definitions = mergeTypeDefs(['type Query { item: Item }', 'type Item { id: ID!, title: String! }']);
  const executable = makeExecutableSchema({typeDefs: definitions});
  assert.ok(executable.getQueryType().getFields().item);
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'ci-medusa-codegen-'));
  try {
    await medusaUtils.gqlSchemaToTypes({
      schema: buildSchema('scalar DateTime\nscalar JSON\ntype Query { item: Item }\ntype Item { id: ID!, title: String!, metadata: JSON, created_at: DateTime }'),
      outputDir: directory, filename: 'query', interfaceName: 'RemoteQueryEntryPoints',
      joinerConfigs: [{alias:{name:'item',entity:'Item'}}],
    });
    const output = fs.readFileSync(path.join(directory, 'query.d.ts'), 'utf8');
    assert.match(output, /export type Item/);
    assert.match(output, /item: Item/);
    assert.match(output, /Record<string, unknown>/);
    assert.match(output, /Date \| string/);
  } finally {
    fs.rmSync(directory, {recursive:true,force:true});
  }
  console.log('CI dependency security and Medusa compatibility checks passed');
}
main().catch((error) => { console.error(error); process.exitCode = 1; });
