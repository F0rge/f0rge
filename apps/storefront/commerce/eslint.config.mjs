import { defineConfig } from "eslint/config";
import medusa from "@medusajs/eslint-plugin";
import { nxBoundaryConfig } from "../../../eslint/nx-boundaries.mjs";

export default defineConfig([...nxBoundaryConfig, ...medusa.configs.recommended]);
