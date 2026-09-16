import type { NextConfig } from "next";
import path from "path";

const repoRoot = path.join(import.meta.dirname, "../../..");

const nextConfig: NextConfig = {
  output: "standalone",
  outputFileTracingRoot: repoRoot,
  turbopack: { root: repoRoot },
  agentRules: false,
  allowedDevOrigins: ["127.0.0.1", "localhost"],
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${process.env.API_URL || "http://localhost:8003"}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
