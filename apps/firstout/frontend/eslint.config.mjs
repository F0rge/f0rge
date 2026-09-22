import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";
import { nxBoundaryConfig } from "../../../eslint/nx-boundaries.mjs";

const firstoutRestrictedImports = {
  "no-restricted-imports": [
    "error",
    {
      paths: [
        {
          name: "@f0rge/ui",
          message: "Firstout uses IBM Carbon (@carbon/react), not @f0rge/ui.",
        },
        {
          name: "@f0rge/ui/forms",
          message: "Firstout uses IBM Carbon (@carbon/react), not @f0rge/ui.",
        },
        {
          name: "@f0rge/ui/api",
          message: "Firstout uses IBM Carbon (@carbon/react), not @f0rge/ui.",
        },
        {
          name: "@base-ui/react",
          message: "Firstout uses IBM Carbon (@carbon/react), not @f0rge/ui engines.",
        },
        {
          name: "@mantine/core",
          message: "Firstout uses IBM Carbon (@carbon/react), not @f0rge/ui engines.",
        },
        {
          name: "@mantine/hooks",
          message: "Firstout uses IBM Carbon (@carbon/react), not @f0rge/ui engines.",
        },
      ],
      patterns: [
        {
          group: ["@f0rge/ui/*", "@base-ui/react/*", "@mantine/*"],
          message: "Firstout uses IBM Carbon (@carbon/react), not @f0rge/ui.",
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
    rules: firstoutRestrictedImports,
  },
  globalIgnores([".next/**", "out/**", "build/**", "next-env.d.ts", ".superdesign/**"]),
]);

export default eslintConfig;
