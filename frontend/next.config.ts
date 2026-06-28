import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Produces a minimal .next/standalone directory, This lets the production Docker image skip copying the full node_modules tree, keeping the final image small.
  output: "standalone",
};

export default nextConfig;
