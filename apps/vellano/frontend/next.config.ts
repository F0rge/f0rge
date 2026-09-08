import type { NextConfig } from "next";
import path from "path";

const repoRoot = path.join(import.meta.dirname, "../../..");

const nextConfig: NextConfig = {
  output: "standalone",
  outputFileTracingRoot: repoRoot,
  turbopack: { root: repoRoot },
  transpilePackages: ["@carbon/react", "@carbon/icons-react", "jspreadsheet-ce", "jsuites"],
  async rewrites() {
    // App Router routes under src/app/api/v1/nia/threads/[threadId]/{run,resume}
    // win over this rewrite (afterFiles) so SSE is piped, not buffered.
    return [
      {
        source: "/api/:path*",
        destination: `${process.env.API_URL || "http://localhost:8003"}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
