import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Produces a minimal .next/standalone directory containing only the
  // node_modules actually needed at runtime, traced from the build graph.
  // This lets the production Docker image skip copying the full
  // node_modules tree, keeping the final image small.
  output: "standalone",
};

export default nextConfig;
