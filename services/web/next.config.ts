import type { NextConfig } from "next";

const apiInternal = process.env.API_INTERNAL_URL || "http://127.0.0.1:8090";

const nextConfig: NextConfig = {
  output: "standalone",
  // LLM-ответ через gateway/rag/inference занимает 1–2 мин; дефолт Next — 30 с → socket hang up / HTTP 500
  experimental: {
    proxyTimeout: 300_000,
  },
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${apiInternal}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
