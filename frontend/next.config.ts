import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
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
