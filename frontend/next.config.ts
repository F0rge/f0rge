import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  // ponytail: CI (ci-develop.yml / ci-main.yml) already runs `npm run typecheck`
  // and `npm run lint` on every PR, so re-running them inside the Docker build on
  // the Pi is redundant memory + time. Skipping them here cuts the build's peak
  // RAM, which is what OOM-kills it under concurrent-build pressure. If CI ever
  // stops gating types/lint, remove these.
  typescript: { ignoreBuildErrors: true },
  eslint: { ignoreDuringBuilds: true },
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
