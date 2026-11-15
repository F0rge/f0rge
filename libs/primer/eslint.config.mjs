import { defineConfig, globalIgnores } from "eslint/config";
import { nxBoundaryLibConfig } from "../../eslint/nx-boundaries.mjs";
export default defineConfig([
  ...nxBoundaryLibConfig,
  globalIgnores(["dist/**"]),
]);
