// Synthetic Access trust-boundary fixture. Never used by production Compose.
import {createServer, request} from 'node:http';
import {generateKeyPairSync, sign} from 'node:crypto';

const host = process.env.FIXTURE_BIND || '127.0.0.1';
if (!['127.0.0.1', '0.0.0.0'].includes(host) || process.env.BUYCYCLE_FIXTURE !== '1') {
  throw new Error('Explicit synthetic fixture mode required');
}
const issuerPort = Number(process.env.FIXTURE_ISSUER_PORT || '9090');
const gatewayPort = Number(process.env.FIXTURE_GATEWAY_PORT || '8090');
if (![issuerPort, gatewayPort].every(port => Number.isInteger(port) && port > 0 && port <= 65535)) throw new Error('Invalid fixture port');
const issuer = `http://127.0.0.1:${issuerPort}`;
const upstream = process.env.FIXTURE_UPSTREAM || 'http://127.0.0.1:8088';
const target = new URL(upstream);
if (!['127.0.0.1', 'localhost'].includes(target.hostname)) throw new Error('Loopback app required');
const {privateKey, publicKey} = generateKeyPairSync('rsa', {modulusLength: 2048});
const key = {...publicKey.export({format: 'jwk'}), kid: 'synthetic-local', alg: 'RS256', use: 'sig'};
const encode = value => Buffer.from(JSON.stringify(value)).toString('base64url');
function assertion(mode) {
  const now = Math.floor(Date.now() / 1000);
  const claims = {iss: issuer, aud: ['buycycle-local'], sub: 'synthetic-owner', email: 'owner@example.test', iat: now, nbf: now - 1, exp: now + 300};
  if (mode === 'denied') claims.email = 'unapproved@example.test';
  if (mode === 'expired') claims.exp = now - 60;
  if (mode === 'wrong-audience') claims.aud = ['other-app'];
  const signing = `${encode({alg: 'RS256', kid: key.kid, typ: 'JWT'})}.${encode(claims)}`;
  return `${signing}.${sign('RSA-SHA256', Buffer.from(signing), privateKey).toString('base64url')}`;
}
createServer((req, res) => {
  if (req.url !== '/cdn-cgi/access/certs') {res.writeHead(404).end(); return;}
  res.writeHead(200, {'Content-Type': 'application/json', 'Cache-Control': 'no-store'});
  res.end(JSON.stringify({keys: [key]}));
}).listen(issuerPort, host);

createServer((req, res) => {
  // HTTP absolute-form and protocol-relative URLs must never replace the app.
  if (!req.url?.startsWith('/') || req.url.startsWith('//')) {
    res.writeHead(400).end('Origin-form path required'); return;
  }
  const destination = new URL(req.url, target);
  if (destination.origin !== target.origin) {
    res.writeHead(400).end('Local app origin required'); return;
  }
  // Only this synthetic gateway accepts a test-state cookie. Real Access does not.
  const mode = (req.headers.cookie || '').match(/(?:^|;\s*)buycycle_fixture=([^;]+)/)?.[1] || 'allowed';
  const headers = {...req.headers};
  delete headers['cf-access-jwt-assertion'];
  delete headers['cf-access-authenticated-user-email'];
  delete headers.authorization;
  if (mode !== 'missing') headers['cf-access-jwt-assertion'] = mode === 'forged' ? 'synthetic.invalid.signature' : assertion(mode);
  headers.host = target.host;
  const proxy = request(destination, {method: req.method, headers}, response => {
    res.writeHead(response.statusCode, response.headers);
    response.pipe(res);
  });
  proxy.on('error', () => res.writeHead(503, {'Content-Type': 'text/plain'}).end('Local app is starting'));
  req.pipe(proxy);
}).listen(gatewayPort, host, () => console.log(`Synthetic Access gateway ready on port ${gatewayPort}; no real identity provider is contacted.`));
