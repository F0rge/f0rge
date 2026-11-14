import { spawnSync } from "node:child_process";
import { randomBytes } from "node:crypto";

function docker(args, capture = false) {
  const result = spawnSync("docker", args, {
    encoding: "utf8",
    stdio: capture ? "pipe" : "inherit",
  });
  if (result.error) throw result.error;
  if (result.status !== 0) throw new Error(`Docker failed with exit ${result.status}`);
  return result.stdout?.trim();
}

const image = process.argv[2];
if (!image || !/^[a-z0-9][a-z0-9/_.:@-]+$/.test(image)) {
  throw new Error("Pass exactly one local image reference to test");
}
const name = `firstout-release-smoke-${randomBytes(8).toString("hex")}`;
const probe = String.raw`
const assert = require('node:assert/strict');
(async () => {
  const base = 'http://127.0.0.1:3000';
  let ready = false;
  for (let attempt = 0; attempt < 60; attempt++) {
    try {
      const response = await fetch(base + '/healthz', { headers: { host: 'healthcheck.railway.app' } });
      if (response.status === 200) {
        assert.deepEqual(await response.json(), { status: 'ok' });
        assert.equal(response.headers.get('cache-control'), 'no-store');
        ready = true;
        break;
      }
    } catch {}
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  assert.ok(ready, 'Firstout healthcheck did not become ready');
  const denied = await fetch(base + '/onboarding', { headers: { host: 'untrusted.example.com' } });
  assert.equal(denied.status, 404, 'Unknown hosts must remain denied');
  const fs = require('node:fs');
  const path = require('node:path');
  const staticRoot = '/app/apps/firstout/frontend/.next/static';
  function assets(dir) {
    return fs.readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
      const file = path.join(dir, entry.name);
      return entry.isDirectory() ? assets(file) : [file];
    });
  }
  const files = assets(staticRoot);
  const javascript = files.find((file) => file.endsWith('.js'));
  const stylesheet = files.find((file) => file.endsWith('.css'));
  assert.ok(javascript && stylesheet, 'Built JavaScript and Carbon CSS must be present');
  const scriptText = files.filter((file) => file.endsWith('.js')).map((file) => fs.readFileSync(file, 'utf8')).join('\n');
  for (const marker of ['Choose your business', 'Your businesses', 'Create business']) {
    assert.ok(scriptText.includes(marker), 'The release must contain the approved business-picker UI: ' + marker);
  }
  const styleText = files.filter((file) => file.endsWith('.css')).map((file) => fs.readFileSync(file, 'utf8')).join('\n');
  assert.ok(styleText.includes('firstout-header-organisation'), 'The release must contain the approved ribbon layout');
  assert.ok(!styleText.includes('firstout-header-create'), 'The removed ribbon creation link must not be restored');
  for (const file of [javascript, stylesheet]) {
    const route = '/_next/static/' + path.relative(staticRoot, file).split(path.sep).join('/');
    const response = await fetch(base + route, { headers: { host: 'firstout.co.za' } });
    assert.equal(response.status, 200, 'Built assets must be served');
    assert.equal(Buffer.from(await response.arrayBuffer()).length, fs.statSync(file).size);
  }
  console.log('Firstout container smoke passed: readiness, host guard, served assets and approved business-picker/ribbon build');
})().catch((error) => { console.error(error); process.exitCode = 1; });
`;

try {
  docker(["run", "--detach", "--platform", "linux/amd64", "--name", name, "--network", "none", "--env", "HOSTNAME=0.0.0.0", image]);
  docker(["exec", name, "node", "-e", probe]);
} catch (error) {
  docker(["logs", name]);
  throw error;
} finally {
  docker(["rm", "--force", name]);
}
