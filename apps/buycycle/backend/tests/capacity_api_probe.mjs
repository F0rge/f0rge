// Synthetic full-size API capacity probe. No response records are logged.
import {createHash} from 'node:crypto';
import {performance} from 'node:perf_hooks';

const base = 'http://127.0.0.1:8090';
const mode = process.env.CAPACITY_MODE;
if (!['bikes', 'wheels', 'concurrent', 'concurrent-bikes'].includes(mode)) throw Error('Explicit capacity mode required');
const expected = {bikes: {items: 28180, history: 495078, models: 750}, wheels: {items: 9394, history: 165042, models: 250}};
let sampling = true;
const health = [];
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
async function requestHealth(path) {
  const started = performance.now();
  try {
    const response = await fetch(base + path, {signal: AbortSignal.timeout(2000)});
    await response.arrayBuffer();
    return {path, status: response.status, milliseconds: Math.round(performance.now() - started)};
  } catch {
    return {path, status: 0, milliseconds: Math.round(performance.now() - started)};
  }
}
const observer = (async () => {
  while (sampling) {
    health.push(await requestHealth('/health'));
    health.push(await requestHealth('/ready'));
    health.push(await requestHealth('/api/v1/status'));
    await sleep(250);
  }
})();
async function report(kind, decode) {
  const started = performance.now();
  const response = await fetch(base + '/api/v1/listings?kind=' + kind, {signal: AbortSignal.timeout(120000)});
  const hash = createHash('sha256');
  let bytes = 0;
  const chunks = [];
  for await (const chunk of response.body) {
    hash.update(chunk);
    bytes += chunk.length;
    if (decode) chunks.push(chunk);
  }
  const result = {kind, status: response.status, milliseconds: Math.round(performance.now() - started), bytes, sha256: hash.digest('hex')};
  if (decode && response.ok) {
    const document = JSON.parse(Buffer.concat(chunks).toString('utf8'));
    const history = document.items.reduce((total, item) => total + item.history.length, 0);
    Object.assign(result, {items: document.items.length, models: document.models.length, alerts: document.alerts.length,
      active: document.active, gone: document.gone, quarantined: document.quarantined.length, history});
    if (result.items !== expected[kind].items || history !== expected[kind].history || result.quarantined !== 0 ||
        result.models !== expected[kind].models || result.active + result.gone !== result.items) throw Error('Synthetic report lost rows/history/models or returned incomplete data');
  }
  if (response.status !== 200 || bytes < 1024) throw Error('Complete synthetic report unavailable');
  return result;
}
const results = [];
let failure = false;
try {
  if (mode === 'concurrent' || mode === 'concurrent-bikes') {
    // Drain concurrent bodies incrementally so the load generator does not add
    // two complete response trees to its own memory. Single requests above
    // independently validate their entire shape and every history-point count.
    results.push(...await Promise.all([report('bikes', false), report(mode === 'concurrent-bikes' ? 'bikes' : 'wheels', false)]));
  } else {
    results.push(await report(mode, true));
    results.push(await report(mode, true));
  }
} catch {
  failure = true;
}
sampling = false;
await observer;
const observedPaths = new Set(health.map(result => result.path));
const passed = !failure && results.length === 2 && ['/health', '/ready', '/api/v1/status'].every(path => observedPaths.has(path)) && health.every(result => result.status === 200);
console.log(JSON.stringify({mode, passed, results, health}));
process.exitCode = passed ? 0 : 1;
