import assert from 'node:assert/strict';
import {createServer, request} from 'node:http';
import {spawn} from 'node:child_process';
import {once} from 'node:events';
import test from 'node:test';

async function listen(server) {server.listen(0, '127.0.0.1'); await once(server, 'listening'); return server.address().port;}
async function freePort() {const server = createServer(); const port = await listen(server); await new Promise(resolve => server.close(resolve)); return port;}
function raw(port, path, headers = {}) {
  return new Promise((resolve, reject) => {
    const req = request({host:'127.0.0.1', port, path, headers}, res => {res.resume(); res.on('end', () => resolve(res.statusCode));});
    req.on('error', reject); req.end();
  });
}
test('synthetic gateway rejects origin overrides before forwarding assertions', async t => {
  let upstreamCalls = 0, attackerCalls = 0;
  const app = createServer((req, res) => {
    upstreamCalls++;
    assert.ok(req.headers['cf-access-jwt-assertion']);
    assert.equal(req.headers.authorization, undefined);
    assert.equal(req.headers['cf-access-authenticated-user-email'], undefined);
    res.end('safe synthetic upstream');
  });
  const attacker = createServer((_req, res) => {attackerCalls++; res.end('must never receive the assertion');});
  const appPort = await listen(app), attackerPort = await listen(attacker);
  t.after(() => {app.close(); attacker.close();});
  const issuerPort = await freePort(), gatewayPort = await freePort();
  const child = spawn(process.execPath, [new URL('./local-access.mjs', import.meta.url).pathname], {
    env:{...process.env, BUYCYCLE_FIXTURE:'1', FIXTURE_UPSTREAM:`http://127.0.0.1:${appPort}`, FIXTURE_ISSUER_PORT:String(issuerPort), FIXTURE_GATEWAY_PORT:String(gatewayPort)}, stdio:['ignore','pipe','pipe']
  });
  t.after(async () => {if (child.exitCode === null) {child.kill(); await once(child, 'exit');}});
  await Promise.race([once(child.stdout,'data'), once(child,'exit').then(() => {throw new Error('Fixture startup failed');})]);
  for (const path of [`//127.0.0.1:${attackerPort}/leak`, `http://127.0.0.1:${attackerPort}/leak`, `/\\127.0.0.1:${attackerPort}/leak`]) {
    assert.equal(await raw(gatewayPort,path),400,path);
  }
  assert.equal(attackerCalls,0);
  assert.equal(upstreamCalls,0);
  assert.equal(await raw(gatewayPort,'/safe',{Authorization:'Bearer synthetic-forged', 'Cf-Access-Authenticated-User-Email':'forged@example.test'}),200);
  assert.equal(upstreamCalls,1);
});
