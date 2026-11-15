// Runs inside the isolated synthetic test network, against the exact app image.
import assert from 'node:assert/strict';
const gateway = 'http://127.0.0.1:8090';
const origin = 'http://127.0.0.1:8080';
let identity;
async function json(path, init = {}, mode = 'allowed') {
  const response = await fetch(gateway + path, {...init, headers: {'Content-Type': 'application/json', Cookie: `buycycle_fixture=${mode}`, ...(identity ? {'X-Buycycle-Expected-Identity': identity} : {}), ...init.headers}});
  return [response, await response.json()];
}
for (let attempt = 0; ; attempt++) {
  try {const res = await fetch(origin + '/ready'); if (res.ok) break;} catch {}
  if (attempt >= 120) throw new Error('Image readiness timeout');
  await new Promise(resolve => setTimeout(resolve, 500));
}
const health = await (await fetch(origin + '/health')).json();
assert.equal(health.source_commit, process.env.SOURCE_COMMIT);
const page = await fetch(gateway + '/');
assert.equal(page.status, 200);
const html = await page.text();
assert.match(html, /id="root"/);
const asset = html.match(/src="([^\"]+\.js)"/);
assert.ok(asset, 'Production JS asset must be served');
assert.equal((await fetch(gateway + asset[1])).status, 200);
for (const [mode, status] of [['missing', 401], ['forged', 401], ['expired', 401], ['wrong-audience', 401], ['denied', 403]]) {
  const [res, body] = await json('/api/v1/state', {}, mode);
  assert.equal(res.status, status, mode);
  assert.ok(body.error.error_id);
  assert.ok(!JSON.stringify(body).includes('owner@example.test'));
}
const direct = await fetch(origin + '/api/v1/state', {headers: {'Cf-Access-Authenticated-User-Email': 'owner@example.test'}});
assert.equal(direct.status, 401, 'Email header alone cannot bypass the origin');
const [statusResponse, status] = await json('/api/v1/status');
assert.equal(statusResponse.status, 200);
identity = status.identity.subject;
assert.ok(identity);
for (const kind of ['bikes', 'wheels']) {
  const [res, listing] = await json('/api/v1/listings?kind=' + kind);
  assert.equal(res.status, 200);
  assert.ok(listing.items.length >= 8, 'Actual PostgreSQL seed must be visible');
  assert.equal(listing.kind, kind);
}
let [res, stored] = await json('/api/v1/state');
assert.equal(res.status, 200);
const write = {expected_revision: stored.revision, state: stored.state};
write.state.bikes.costs.buffer = 37;
assert.equal((await json('/api/v1/state', {method:'PUT', headers:{'X-Buycycle-Expected-Identity':'stale-other-subject'}, body:JSON.stringify(write)}))[0].status,403);
[res, stored] = await json('/api/v1/state', {method: 'PUT', body: JSON.stringify(write)});
assert.equal(res.status, 200);
assert.equal(stored.state.bikes.costs.buffer, 37);
const [conflict] = await json('/api/v1/state', {method: 'PUT', body: JSON.stringify(write)});
assert.equal(conflict.status, 409);
const invalid = structuredClone(stored.state);
invalid.bikes.costs.buffer = -1;
assert.equal((await json('/api/v1/state', {method: 'PUT', body: JSON.stringify({expected_revision: stored.revision, state: invalid})}))[0].status, 422);
const transfer = {expected_revision: stored.revision, state: stored.state, source: {origin: 'synthetic-image-rehearsal', watch: {}, log: [], costs: {buffer: 37}}};
assert.equal((await json('/api/v1/state/import-preview', {method: 'POST', body: JSON.stringify(transfer)}))[0].status, 200);
const first = await json('/api/v1/state/import', {method: 'POST', body: JSON.stringify(transfer)});
const repeat = await json('/api/v1/state/import', {method: 'POST', body: JSON.stringify(transfer)});
assert.equal(first[0].status, 200);
assert.equal(repeat[0].status, 200);
assert.equal(first[1].revision, repeat[1].revision);
console.log(JSON.stringify({production_frontend: true, postgres_records: true, verified_access: true, origin_bypass_denied: true, state_persistence: true, revision_conflict: true, backend_validation: true, import_repeat_safe: true, health_commit: true}));
