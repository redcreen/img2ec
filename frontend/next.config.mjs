/** @type {import('next').NextConfig} */
// 后端 API 地址：API_PROXY_TARGET 优先，否则默认 8001（dev）；prod 启动脚本会注入 8000。
const apiTarget = process.env.API_PROXY_TARGET || 'http://localhost:8001';
const nextConfig = {
  // Codex CLI 调用动辄 1-3 分钟；Next dev 代理默认 30s 切断，到前端就是
  // "Internal Server Error"（500 + 21 字节）。放宽到 10 分钟。
  experimental: {
    proxyTimeout: 600_000,
  },
  async rewrites() {
    return [
      { source: '/api/:path*', destination: `${apiTarget}/api/:path*` },
      { source: '/static/:path*', destination: `${apiTarget}/static/:path*` },
    ];
  },
};
export default nextConfig;
