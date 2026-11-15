import fs from "node:fs";
import path from "node:path";
import os from "node:os";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
const root = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "../../../..",
);
const temporary = fs.mkdtempSync(path.join(os.tmpdir(), "buycycle-contract-"));
try {
  const schema = path.join(root, "apps/buycycle/backend/openapi.json");
  // Required Rust tests separately compare this snapshot against ApiDoc::openapi().
  if (!process.argv.includes("--check")) {
    const exported = spawnSync(
      "cargo",
      [
        "run",
        "--locked",
        "--manifest-path",
        "apps/buycycle/backend/Cargo.toml",
        "--target-dir",
        "target/nx/buycycle-backend",
        "--bin",
        "export-contract",
        "--",
        schema,
      ],
      { cwd: root, stdio: "inherit" },
    );
    if (exported.status !== 0) process.exit(exported.status ?? 1);
  }
  const { default: openapiTS, astToString } = await import(
    "openapi-typescript"
  );
  const generated = astToString(
    await openapiTS(JSON.parse(fs.readFileSync(schema, "utf8"))),
  );
  const target = path.join(root, "apps/buycycle/frontend/src/api/generated.ts");
  if (process.argv.includes("--check")) {
    if (!fs.existsSync(target) || fs.readFileSync(target, "utf8") !== generated)
      throw new Error(
        "Rust API/client drift: run npm run codegen -w @f0rge/buycycle-frontend",
      );
  } else {
    fs.mkdirSync(path.dirname(target), { recursive: true });
    fs.writeFileSync(target, generated);
  }
} finally {
  fs.rmSync(temporary, { recursive: true, force: true });
}
