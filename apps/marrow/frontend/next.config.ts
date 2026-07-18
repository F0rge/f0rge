import type { NextConfig } from "next";
import path from "path";

// Repo root, three levels up from apps/marrow/frontend. Pinning both the file
// tracing root and the turbopack root here stops Next from mis-inferring the
// monorepo root (which breaks standalone output layout) and prepares for the
// shared libs/ workspace landing in P5. import.meta.dirname, not __dirname:
// this file is an ES module — __dirname crashes @nx/next's graph processing.
const repoRoot = path.join(import.meta.dirname, "../../..");

const nextConfig: NextConfig = {
  output: "standalone",
  outputFileTracingRoot: repoRoot,
  turbopack: { root: repoRoot },
  // @f0rge/ui is raw TS (internal-package pattern, no build step) — Next must
  // transpile it.
  transpilePackages: ["@f0rge/ui"],
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: `${process.env.API_URL || 'http://localhost:8000'}/api/:path*`,
      },
    ]
  },
};

export default nextConfig;
