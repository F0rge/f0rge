/**
 * Ban direct UI engine imports in app frontends — use @f0rge/ui instead.
 * Spread into each app's eslint.config.mjs (not libs/ui).
 */

const RESTRICTED_MESSAGE =
  "Import UI from @f0rge/ui or @f0rge/ui/forms. UI engines (@base-ui, @mantine/*) are only allowed in libs/ui.";

const restrictedUiEnginesRule = {
  "no-restricted-imports": [
    "error",
    {
      paths: [
        {
          name: "@base-ui/react",
          message: RESTRICTED_MESSAGE,
        },
        {
          name: "@mantine/core",
          message: RESTRICTED_MESSAGE,
        },
        {
          name: "@mantine/hooks",
          message: RESTRICTED_MESSAGE,
        },
        {
          name: "@mantine/form",
          message: RESTRICTED_MESSAGE,
        },
      ],
      patterns: [
        {
          group: ["@base-ui/react/*"],
          message: RESTRICTED_MESSAGE,
        },
        {
          group: ["@mantine/core/*"],
          message: RESTRICTED_MESSAGE,
        },
        {
          group: ["@mantine/hooks/*"],
          message: RESTRICTED_MESSAGE,
        },
      ],
    },
  ],
};

/**
 * Flat-config fragment for app frontends. `files` are relative to the project root.
 */
export const restrictedUiEnginesConfig = [
  {
    files: ["**/*.{ts,tsx,js,jsx}"],
    rules: restrictedUiEnginesRule,
  },
];
