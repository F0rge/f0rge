import { existsSync, readFileSync } from "node:fs"
import { join } from "node:path"

type LockPackage = {
  version?: string
  dev?: boolean
  dependencies?: Record<string, string>
}

function repoRoot(start: string): string {
  let dir = start
  for (let i = 0; i < 8; i += 1) {
    if (existsSync(join(dir, "nx.json")) && existsSync(join(dir, "package-lock.json"))) {
      return dir
    }
    const parent = join(dir, "..")
    if (parent === dir) break
    dir = parent
  }
  throw new Error(`repo root not found from ${start}`)
}

test("commerce production install hoists uuid where @medusajs/core-flows can require it", () => {
  const root = repoRoot(__dirname)
  const manifest = JSON.parse(readFileSync(join(root, "package.json"), "utf8")) as {
    dependencies: Record<string, string>
  }
  const lock = JSON.parse(readFileSync(join(root, "package-lock.json"), "utf8")) as {
    packages: Record<string, LockPackage>
  }

  // core-flows calls require("uuid") and does not declare it. Node resolves that
  // from the hoisted node_modules/uuid slot. The commerce image's
  // `npm ci --workspace=@f0rge/storefront-commerce --include-workspace-root=false`
  // omits root devDependencies, so a dev-only uuid@9 in that slot is absent and
  // medusa start dies with Cannot find module 'uuid'.
  expect(lock.packages["node_modules/@medusajs/core-flows"]?.dependencies?.uuid).toBeUndefined()
  expect(manifest.dependencies.uuid).toBe("11.1.1")

  const hoisted = lock.packages["node_modules/uuid"]
  expect(hoisted?.version).toBe("11.1.1")
  expect(hoisted?.dev).toBeUndefined()

  const pythonUuid = lock.packages["node_modules/@nxlv/python/node_modules/uuid"]
  expect(pythonUuid?.version).toBe("9.0.1")
  expect(pythonUuid?.dev).toBe(true)
})
