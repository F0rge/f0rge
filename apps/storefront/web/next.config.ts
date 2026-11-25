import type { NextConfig } from "next";
import path from "path";

const repoRoot = path.join(import.meta.dirname, "../../..");
const privateReferrerPaths = [
  "/account/orders/:path*",
  "/api/account/orders/:path*",
  "/order/confirmation/:path*",
  "/api/order/confirmation/:path*",
  "/checkout/paystack-return",
];

const nextConfig: NextConfig = {
  agentRules: false,
  allowedDevOrigins: ["127.0.0.1"],
  output: "standalone",
  outputFileTracingRoot: repoRoot,
  turbopack: { root: repoRoot },
  transpilePackages: ["@f0rge/ui"],
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "Strict-Transport-Security", value: "max-age=31536000" },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "X-Frame-Options", value: "DENY" },
        ],
      },
      ...privateReferrerPaths.map((source) => ({
        source,
        headers: [{ key: "Referrer-Policy", value: "no-referrer" }],
      })),
    ];
  },
};

export default nextConfig;
