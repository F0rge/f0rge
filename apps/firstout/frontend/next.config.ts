import type { NextConfig } from "next";
import path from "path";

const repoRoot = path.join(import.meta.dirname, "../../..");

const nextConfig: NextConfig = {
  output: "standalone",
  outputFileTracingRoot: repoRoot,
  turbopack: { root: repoRoot },
  // The owner-only catalogue ZIP contains up to 40 MiB plus multipart framing.
  experimental: { proxyClientMaxBodySize: "42mb" },
  allowedDevOrigins: ["127.0.0.1", "localhost"],
  transpilePackages: ["@carbon/react", "@carbon/icons-react"],
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
