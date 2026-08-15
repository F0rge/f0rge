import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";
import { nxBoundaryConfig } from "../../../../eslint/nx-boundaries.mjs";
import { restrictedUiEnginesConfig } from "../../../../eslint/restricted-ui-engines.mjs";

const eslintConfig = defineConfig([
  ...nxBoundaryConfig,
  ...restrictedUiEnginesConfig,
  ...nextVitals,
  ...nextTs,
  globalIgnores([".next/**", "out/**", "build/**", "next-env.d.ts"]),
]);

export default eslintConfig;
