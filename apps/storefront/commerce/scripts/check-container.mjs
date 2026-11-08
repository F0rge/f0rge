import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const root = fileURLToPath(new URL("../../../../", import.meta.url));
const git = spawnSync("git", ["rev-parse", "HEAD"], { cwd: root, encoding: "utf8" });
if (git.status !== 0) throw new Error("Cannot identify the source commit for the container check");
const source = process.env.GITHUB_SHA || git.stdout.trim();
const run = process.env.GITHUB_RUN_ID || `local-${process.pid}-${Date.now()}`;
const attempt = process.env.GITHUB_RUN_ATTEMPT || "1";
const tag = `${source.slice(0, 40)}-${run}-${attempt}`.toLowerCase().replace(/[^a-z0-9_.-]/g, "-");
const image = `f0rge-daskasas-commerce-test:${tag}`;

function docker(args) {
  const result = spawnSync("docker", args, { cwd: root, stdio: "inherit" });
  if (result.error) throw result.error;
  if (result.status !== 0) throw new Error(`Container check failed (exit ${result.status})`);
}

const probe = String.raw`
const assert = require('node:assert/strict');
const fs = require('node:fs');
require('@medusajs/core-flows');
assert.equal(typeof require('uuid').v4, 'function');
const marker = '/usr/local/share/daskasas/hosted-artifact';
assert.equal(fs.statSync(marker).uid, 0);
assert.throws(() => fs.accessSync(marker, fs.constants.W_OK));
assert.throws(() => fs.accessSync('/usr/local/share/daskasas', fs.constants.W_OK));
const { testPaymentEnabled } = require('./src/test-payment-config');
const { assertHostedCommerceConfig } = require('./src/hosted-commerce-config');
process.argv = [process.execPath, 'medusa', 'develop', '--host', '127.0.0.1'];
const local = {
  NODE_ENV: 'development', HOST: '127.0.0.1', STOREFRONT_RUNTIME_KIND: 'local',
  STOREFRONT_TEST_PAYMENT_ENABLED: 'true', DATABASE_URL: 'postgres://test:test@localhost/shop',
  REDIS_URL: 'redis://localhost:6379', STOREFRONT_PUBLIC_URL: 'http://localhost:3004',
  STORE_CORS: 'http://localhost:3004', ADMIN_CORS: 'http://localhost:9000', AUTH_CORS: 'http://localhost:3004',
};
assert.throws(() => testPaymentEnabled(local), /disabled on hosted/i);
assert.throws(() => testPaymentEnabled({ ...local, NODE_ENV: 'test', STOREFRONT_RUNTIME_KIND: 'test' }), /disabled on hosted/i);
assert.throws(() => assertHostedCommerceConfig(local), /JWT_SECRET/);
assert.throws(() => assertHostedCommerceConfig({}), /DATABASE_URL/);
assertHostedCommerceConfig({ ...local, JWT_SECRET: 'j'.repeat(32), COOKIE_SECRET: 'c'.repeat(32), STOREFRONT_BFF_SECRET: 'b'.repeat(32) });
console.log('Commerce image: runtime imports and immutable hosted guard PASS');
`;

try {
  docker(["build", "--target", "runner", "-t", image, "-f", "apps/storefront/commerce/Dockerfile", "."]);
  docker(["run", "--rm", "--network", "none", "--user", "node", "--entrypoint", "node", image, "-e", probe]);
} finally {
  // Remove only this check's tag; never prune shared Docker state.
  spawnSync("docker", ["image", "rm", image], { cwd: root, stdio: "ignore" });
}
