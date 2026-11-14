import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import { chmodSync, existsSync, mkdtempSync, readFileSync, rmSync, symlinkSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { delimiter, join } from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";

const script = fileURLToPath(new URL("./check-container.mjs", import.meta.url));
const root = fileURLToPath(new URL("../../../../", import.meta.url));
const commit = "a".repeat(40);
const imageId = `sha256:${"b".repeat(64)}`;

function fixture(t) {
  const dir = mkdtempSync(join(tmpdir(), "f0rge-container-test-"));
  t.after(() => rmSync(dir, { recursive: true, force: true }));
  const log = join(dir, "calls.jsonl");
  const fake = `#!/usr/bin/env node
const fs = require('node:fs');
const path = require('node:path');
const name = path.basename(process.argv[1]);
const args = process.argv.slice(2);
fs.appendFileSync(process.env.FAKE_CONTAINER_LOG, JSON.stringify({name, args}) + '\\n');
if (name === 'git' && args[0] === 'rev-parse') console.log('${commit}');
if (name === 'git' && args[0] === 'archive') fs.writeFileSync(args[args.indexOf('--output') + 1], 'snapshot');
if (name === 'docker' && args[0] === 'image' && args[1] === 'inspect') {
  console.log(args.includes('{{.Id}}') ? (process.env.FAKE_IMAGE_ID || '${imageId}') : 'linux/amd64');
}
if (name === 'docker' && args[0] === 'run' && process.env.FAKE_RUN_FAILURE) process.exit(1);
if (name === 'docker' && args[0] === 'image' && args[1] === 'save') fs.writeFileSync(args[args.indexOf('--output') + 1], 'test archive');
`;
  for (const name of ["git", "tar", "docker"]) {
    const path = join(dir, name);
    writeFileSync(path, fake);
    chmodSync(path, 0o755);
  }
  return {
    dir,
    run(extra = {}) {
      const env = { ...process.env, PATH: `${dir}${delimiter}${process.env.PATH}`, FAKE_CONTAINER_LOG: log, GITHUB_SHA: commit, GITHUB_ACTIONS: "false", ...extra };
      delete env.F0RGE_COMMERCE_IMAGE_ARCHIVE;
      if (extra.F0RGE_COMMERCE_IMAGE_ARCHIVE) env.F0RGE_COMMERCE_IMAGE_ARCHIVE = extra.F0RGE_COMMERCE_IMAGE_ARCHIVE;
      const result = spawnSync(process.execPath, [script], { cwd: root, env, encoding: "utf8" });
      const calls = existsSync(log) ? readFileSync(log, "utf8").trim().split("\n").map((line) => JSON.parse(line)) : [];
      return { ...result, calls };
    },
  };
}

test("default probes the immutable local image ID offline and cleans its tag", (t) => {
  const f = fixture(t);
  const result = f.run();
  assert.equal(result.status, 0, result.stderr);
  const run = result.calls.find((call) => call.name === "docker" && call.args[0] === "run");
  assert.ok(run.args.includes(imageId));
  assert.ok(run.args.includes("--network") && run.args.includes("none"));
  assert.ok(!result.calls.some((call) => call.args[0] === "archive" || call.args[1] === "save"));
  assert.equal(result.calls.at(-1).args.slice(0, 2).join(" "), "image rm");
});

test("retention builds a commit snapshot and saves the exact tested ID with a separate archive checksum", (t) => {
  const f = fixture(t);
  const archive = join(f.dir, "image.tar");
  const result = f.run({ F0RGE_COMMERCE_IMAGE_ARCHIVE: archive });
  assert.equal(result.status, 0, result.stderr);
  const build = result.calls.find((call) => call.name === "docker" && call.args[0] === "build");
  assert.notEqual(build.args.at(-1), root);
  assert.ok(result.calls.some((call) => call.name === "git" && call.args[0] === "archive" && call.args.at(-1) === commit));
  const run = result.calls.find((call) => call.name === "docker" && call.args[0] === "run");
  const save = result.calls.find((call) => call.name === "docker" && call.args[1] === "save");
  assert.ok(run.args.includes(imageId));
  assert.equal(save.args.at(-1), imageId);
  const evidence = JSON.parse(readFileSync(`${archive}.json`, "utf8"));
  assert.equal(evidence.source_commit, commit);
  assert.equal(evidence.image_id, imageId);
  assert.equal(evidence.platform, "linux/amd64");
  assert.deepEqual(evidence.execution, { mode: "local" });
  assert.equal(evidence.archive_sha256, `sha256:${createHash("sha256").update(readFileSync(archive)).digest("hex")}`);
  assert.match(evidence.note, /not a registry manifest digest/);
});

test("retention records validated GitHub run metadata as self-reported information", (t) => {
  const f = fixture(t);
  const archive = join(f.dir, "image.tar");
  const metadata = { GITHUB_ACTIONS: "true", GITHUB_RUN_ID: "123", GITHUB_RUN_ATTEMPT: "2", GITHUB_WORKFLOW: "CI", GITHUB_EVENT_NAME: "pull_request", GITHUB_WORKFLOW_REF: "F0rge/f0rge/.github/workflows/ci.yml@refs/pull/1/merge" };
  const result = f.run({ ...metadata, F0RGE_COMMERCE_IMAGE_ARCHIVE: archive });
  assert.equal(result.status, 0, result.stderr);
  const evidence = JSON.parse(readFileSync(`${archive}.json`, "utf8"));
  assert.deepEqual(evidence.execution, { mode: "github-actions", run_id: "123", attempt: "2", workflow: "CI", workflow_ref: metadata.GITHUB_WORKFLOW_REF, event: "pull_request" });
  assert.match(evidence.note, /Self-reported/);
  const bad = fixture(t);
  const failed = bad.run({ ...metadata, GITHUB_RUN_ATTEMPT: "0", F0RGE_COMMERCE_IMAGE_ARCHIVE: join(bad.dir, "image.tar") });
  assert.notEqual(failed.status, 0);
  assert.ok(!failed.calls.some((call) => call.name === "docker"));
});

test("failed probes and malformed image IDs never retain an archive", (t) => {
  for (const extra of [{ FAKE_RUN_FAILURE: "1" }, { FAKE_IMAGE_ID: "latest" }]) {
    const f = fixture(t);
    const archive = join(f.dir, "image.tar");
    const result = f.run({ ...extra, F0RGE_COMMERCE_IMAGE_ARCHIVE: archive });
    assert.notEqual(result.status, 0);
    assert.ok(!existsSync(archive));
    assert.ok(!existsSync(`${archive}.json`));
    assert.ok(!result.calls.some((call) => call.name === "docker" && call.args[1] === "save"));
    assert.equal(result.calls.at(-1).args.slice(0, 2).join(" "), "image rm");
  }
});

test("retention rejects inconsistent commit, unsafe or existing output paths without writing", (t) => {
  for (const kind of ["commit", "relative", "inside", "existing", "symlink"]) {
    const f = fixture(t);
    let archive = join(f.dir, "image.tar");
    const extra = {};
    if (kind === "commit") extra.GITHUB_SHA = "c".repeat(40);
    if (kind === "relative") archive = "image.tar";
    if (kind === "inside") archive = join(root, "image.tar");
    if (kind === "existing") writeFileSync(archive, "keep");
    if (kind === "symlink") symlinkSync(join(f.dir, "missing"), archive);
    const result = f.run({ ...extra, F0RGE_COMMERCE_IMAGE_ARCHIVE: archive });
    assert.notEqual(result.status, 0, kind);
    assert.ok(!result.calls.some((call) => call.name === "docker"));
    if (kind === "existing") assert.equal(readFileSync(archive, "utf8"), "keep");
    if (kind === "symlink") assert.ok(!existsSync(join(f.dir, "missing")));
  }
});
