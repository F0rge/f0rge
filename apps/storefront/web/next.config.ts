import type { NextConfig } from "next";
import path from "path";

const repoRoot = path.join(import.meta.dirname, "../../..");

const nextConfig: NextConfig = {
  agentRules: false,
  output: "standalone",
  outputFileTracingRoot: repoRoot,
  turbopack: { root: repoRoot },
  transpilePackages: ["@f0rge/ui"],
};

export default nextConfig;
