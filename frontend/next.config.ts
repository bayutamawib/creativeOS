import type { NextConfig } from "next";
const config: NextConfig = {
  output: "standalone",
  poweredByHeader: false,
  experimental: { cpus: 2 },
  async rewrites() {
    return [
      { source: "/api/:path*", destination: "http://backend:8000/api/:path*" },
    ];
  },
};
export default config;
