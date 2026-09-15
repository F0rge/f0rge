import type { NextConfig } from "next";
import path from "path";

const repoRoot = path.join(import.meta.dirname, "../../..");

const nextConfig: NextConfig = {
  output: "standalone",
  outputFileTracingRoot: repoRoot,
  turbopack: { root: repoRoot },
  agentRules: false,
};

export default nextConfig;
