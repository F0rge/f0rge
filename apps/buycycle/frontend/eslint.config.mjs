import { defineConfig, globalIgnores } from "eslint/config";
import { nxBoundaryLibConfig } from "../../../eslint/nx-boundaries.mjs";
export default defineConfig([
  ...nxBoundaryLibConfig,
  globalIgnores(["dist/**", "src/api/generated.ts"]),
  {
    files: ["src/**/*.{ts,tsx}"],
    rules: {
      "no-restricted-imports": [
        "error",
        {
          paths: [
            {
              name: "@primer/react",
              message: "Use the shared @f0rge/primer bricks.",
            },
          ],
          patterns: ["@mantine/*", "@base-ui/*", "@f0rge/ui"],
        },
      ],
      "@typescript-eslint/no-explicit-any": "error",
    },
  },
]);
