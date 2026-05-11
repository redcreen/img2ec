/** @type {import('next').NextConfig} */
// 后端 API 地址：API_PROXY_TARGET 优先，否则默认 8001（dev）；prod 启动脚本会注入 8000。
const apiTarget = process.env.API_PROXY_TARGET || 'http://localhost:8001';
const nextConfig = {
  async rewrites() {
    return [
      { source: '/api/:path*', destination: `${apiTarget}/api/:path*` },
      { source: '/static/:path*', destination: `${apiTarget}/static/:path*` },
    ];
  },
};
export default nextConfig;
