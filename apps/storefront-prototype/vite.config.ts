import { defineConfig } from "vite";
import tailwindcss from "@tailwindcss/vite";
import { fileURLToPath } from "node:url";
import { realpathSync } from "node:fs";

export default defineConfig({
  plugins: [tailwindcss()],
  resolve: {
    alias: {
      "@f0rge/ui/forms": fileURLToPath(
        new URL("../../libs/ui/src/forms/index.ts", import.meta.url),
      ),
      "@f0rge/ui": fileURLToPath(
        new URL("../../libs/ui/src/index.ts", import.meta.url),
      ),
    },
    dedupe: ["react", "react-dom"],
  },
  server: {
    fs: {
      allow: [
        fileURLToPath(new URL("../..", import.meta.url)),
        realpathSync(
          fileURLToPath(new URL("../../node_modules", import.meta.url)),
        ),
      ],
    },
  },
});
