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
  // ponytail: CI (ci-develop.yml / ci-main.yml) runs `npm run typecheck` on every
  // PR, so re-type-checking inside the Docker build on Fly is redundant memory
  // + time — and peak RAM is what OOM-kills the build under concurrent-build
  // pressure. If CI ever stops gating types, remove this. (This Next version has
  // no in-build ESLint, so there is no eslint key to skip.)
  typescript: { ignoreBuildErrors: true },
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
