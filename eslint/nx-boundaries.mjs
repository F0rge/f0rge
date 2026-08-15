/**
 * Shared Nx module-boundary rules for TypeScript projects.
 * Import into each project's eslint.config.mjs.
 */
import nx from "@nx/eslint-plugin";

const boundaryRule = {
  "@nx/enforce-module-boundaries": [
    "error",
    {
      enforceBuildableLibDependency: false,
      allow: [],
      depConstraints: [
        {
          sourceTag: "scope:shared",
          onlyDependOnLibsWithTags: ["scope:shared"],
        },
        {
          sourceTag: "scope:marrow",
          onlyDependOnLibsWithTags: ["scope:shared", "scope:marrow"],
        },
        {
          sourceTag: "scope:dk",
          onlyDependOnLibsWithTags: ["scope:shared", "scope:dk"],
        },
      ],
    },
  ],
};

/**
 * For Next apps that already use eslint-config-next — only the Nx plugin + boundary rule.
 * Does not pull in flat/typescript (avoids stacking typescript-eslint rules on nextTs).
 */
export const nxBoundaryConfig = [
  ...nx.configs["flat/base"],
  {
    files: ["**/*.ts", "**/*.tsx", "**/*.js", "**/*.jsx"],
    rules: boundaryRule,
  },
];

/**
 * For non-Next libs (e.g. f0rge-ui) that need a TS parser.
 */
export const nxBoundaryLibConfig = [
  ...nx.configs["flat/base"],
  ...nx.configs["flat/typescript"],
  {
    files: ["**/*.ts", "**/*.tsx", "**/*.js", "**/*.jsx"],
    rules: boundaryRule,
  },
];
