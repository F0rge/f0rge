import { spawnSync } from "node:child_process";
import { createHash, randomBytes } from "node:crypto";
import { createReadStream } from "node:fs";
import { linkSync, lstatSync, mkdtempSync, mkdirSync, realpathSync, rmSync, writeFileSync } from "node:fs";
import { basename, dirname, isAbsolute, join, relative } from "node:path";
import { tmpdir } from "node:os";
import { fileURLToPath } from "node:url";

const root = fileURLToPath(new URL("../../../../", import.meta.url));
const git = spawnSync("git", ["rev-parse", "HEAD"], { cwd: root, encoding: "utf8" });
if (git.status !== 0) throw new Error("Cannot identify the source commit for the container check");
const source = git.stdout.trim();
if (!/^[0-9a-f]{40}$/.test(source)) throw new Error("Git HEAD is not a full commit ID");
const requestedArchive = process.env.F0RGE_COMMERCE_IMAGE_ARCHIVE;
if (requestedArchive && ((process.env.GITHUB_SHA && process.env.GITHUB_SHA !== source)
  || (process.env.GITHUB_ACTIONS === "true" && process.env.GITHUB_SHA !== source))) {
  throw new Error("GITHUB_SHA does not match the checked-out commit");
}
const run = process.env.GITHUB_RUN_ID || `local-${process.pid}-${Date.now()}`;
const attempt = process.env.GITHUB_RUN_ATTEMPT || "1";
const tag = `${source.slice(0, 40)}-${run}-${attempt}-${randomBytes(6).toString("hex")}`.toLowerCase().replace(/[^a-z0-9_.-]/g, "-");
const image = `f0rge-daskasas-commerce-test:${tag}`;

function docker(args) {
  const result = spawnSync("docker", args, { cwd: root, stdio: "inherit" });
  if (result.error) throw result.error;
  if (result.status !== 0) throw new Error(`Container check failed (exit ${result.status})`);
}

function output(command, args, cwd = root) {
  const result = spawnSync(command, args, { cwd, encoding: "utf8" });
  if (result.error) throw result.error;
  if (result.status !== 0) throw new Error(`${command} failed (exit ${result.status})`);
  return result.stdout.trim();
}

function exists(path) {
  try { lstatSync(path); return true; } catch (error) {
    if (error.code === "ENOENT") return false;
    throw error;
  }
}

function archivePath(value) {
  if (!isAbsolute(value)) throw new Error("F0RGE_COMMERCE_IMAGE_ARCHIVE must be an absolute path");
  const parent = realpathSync(dirname(value));
  const withinRoot = relative(realpathSync(root), parent);
  if (!withinRoot || (withinRoot !== ".." && !withinRoot.startsWith("../") && !isAbsolute(withinRoot))) {
    throw new Error("Image archive must be outside the repository");
  }
  const path = join(parent, basename(value));
  if (exists(path) || exists(`${path}.json`)) throw new Error("Image archive or evidence already exists");
  return path;
}

function executionMetadata() {
  if (process.env.GITHUB_ACTIONS !== "true") return { mode: "local" };
  const runId = process.env.GITHUB_RUN_ID;
  const attempt = process.env.GITHUB_RUN_ATTEMPT;
  const workflow = process.env.GITHUB_WORKFLOW;
  const event = process.env.GITHUB_EVENT_NAME;
  const workflowRef = process.env.GITHUB_WORKFLOW_REF;
  if (!/^[1-9][0-9]{0,19}$/.test(runId || "") || !/^[1-9][0-9]{0,9}$/.test(attempt || "")
    || !workflow || workflow.length > 200 || /[\u0000-\u001f\u007f]/.test(workflow)
    || !/^[a-z][a-z_]{0,79}$/.test(event || "")
    || !workflowRef || workflowRef.length > 400 || /[\u0000-\u001f\u007f]/.test(workflowRef)) {
    throw new Error("Invalid or incomplete GitHub Actions run metadata");
  }
  return { mode: "github-actions", run_id: runId, attempt, workflow, workflow_ref: workflowRef, event };
}

async function retain(imageId, platform, destination, execution) {
  const temporary = mkdtempSync(join(dirname(destination), ".f0rge-commerce-"));
  const archive = join(temporary, "image.tar");
  const evidence = join(temporary, "evidence.json");
  let archiveLinked = false;
  try {
    docker(["image", "save", "--output", archive, imageId]);
    const hash = createHash("sha256");
    for await (const chunk of createReadStream(archive)) hash.update(chunk);
    writeFileSync(evidence, JSON.stringify({
      schema: "f0rge-commerce-local-image-v1",
      source_commit: source,
      image_id: imageId,
      platform,
      archive_sha256: `sha256:${hash.digest("hex")}`,
      test: "offline-commerce-runtime-probe",
      execution,
      note: "Self-reported metadata, local image ID and archive checksum are not a registry manifest digest or signed provenance.",
    }, null, 2) + "\n", { flag: "wx" });
    // Hard-link creation fails if either destination exists, including a symlink.
    linkSync(archive, destination);
    archiveLinked = true;
    linkSync(evidence, `${destination}.json`);
    archiveLinked = false;
    console.log(`Retained tested image archive and local evidence: ${destination}`);
  } finally {
    if (archiveLinked) rmSync(destination, { force: true });
    rmSync(temporary, { recursive: true, force: true });
  }
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

let snapshot;
let buildContext = root;
const destination = requestedArchive ? archivePath(requestedArchive) : undefined;
const execution = destination ? executionMetadata() : undefined;
try {
  if (destination) {
    // Only retention uses a pristine committed source snapshot. Dirty or untracked
    // working-tree files cannot silently become part of the retained image.
    snapshot = mkdtempSync(join(tmpdir(), "f0rge-commerce-context-"));
    buildContext = join(snapshot, "source");
    mkdirSync(buildContext);
    const archive = join(snapshot, "source.tar");
    output("git", ["archive", "--format=tar", "--output", archive, source]);
    output("tar", ["-xf", archive, "-C", buildContext]);
  }
  docker(["build", "--target", "runner", "-t", image, "-f", join(buildContext, "apps/storefront/commerce/Dockerfile"), buildContext]);
  const imageId = output("docker", ["image", "inspect", "--format", "{{.Id}}", image]);
  if (!/^sha256:[0-9a-f]{64}$/.test(imageId)) throw new Error("Docker returned an invalid image ID");
  const platform = output("docker", ["image", "inspect", "--format", "{{.Os}}/{{.Architecture}}", imageId]);
  if (!/^linux\/[a-z0-9_]+$/.test(platform)) throw new Error("Docker returned an invalid image platform");
  docker(["run", "--rm", "--network", "none", "--user", "node", "--entrypoint", "node", imageId, "-e", probe]);
  if (destination) await retain(imageId, platform, destination, execution);
} finally {
  // Remove only this check's tag; never prune shared Docker state.
  spawnSync("docker", ["image", "rm", image], { cwd: root, stdio: "ignore" });
  if (snapshot) rmSync(snapshot, { recursive: true, force: true });
}
