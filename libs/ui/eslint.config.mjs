import { defineConfig, globalIgnores } from "eslint/config";
import { nxBoundaryLibConfig } from "../../eslint/nx-boundaries.mjs";

/** Lib-level ESLint — Nx boundaries + TS parse (no eslint-config-next). */
export default defineConfig([
  ...nxBoundaryLibConfig,
  globalIgnores(["dist/**", "storybook-static/**"]),
]);
