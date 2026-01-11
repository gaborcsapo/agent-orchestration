/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    return [
      // Arena API proxy
      {
        source: '/api/arena/:path*',
        destination: 'http://localhost:8000/api/:path*',
      },
      // Agent A API proxy
      {
        source: '/api/agent-a/:path*',
        destination: 'http://localhost:8001/api/:path*',
      },
      // Agent B API proxy
      {
        source: '/api/agent-b/:path*',
        destination: 'http://localhost:8002/api/:path*',
      },
    ]
  },
}

module.exports = nextConfig
