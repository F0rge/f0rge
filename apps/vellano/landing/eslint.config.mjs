import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";
import { nxBoundaryConfig } from "../../../eslint/nx-boundaries.mjs";

const landingRestrictedImports = {
  "no-restricted-imports": [
    "error",
    {
      paths: [
        { name: "@f0rge/ui", message: "The landing app has its own design; do not import @f0rge/ui." },
        { name: "@carbon/react", message: "The landing app does not use IBM Carbon." },
      ],
      patterns: [
        {
          group: ["@f0rge/ui/*", "@carbon/*"],
          message: "The landing app has its own design; no shared UI kits.",
        },
      ],
    },
  ],
};

const eslintConfig = defineConfig([
  ...nxBoundaryConfig,
  ...nextVitals,
  ...nextTs,
  {
    files: ["**/*.{ts,tsx,js,jsx}"],
    rules: landingRestrictedImports,
  },
  globalIgnores([".next/**", "out/**", "build/**", "next-env.d.ts"]),
]);

export default eslintConfig;
