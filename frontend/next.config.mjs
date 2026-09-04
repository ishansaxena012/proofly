/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Produces a self-contained .next/standalone server bundle for the Dockerfile.
  output: "standalone",
  eslint: {
    // Lint is run explicitly via `npm run lint`; keep `next build` focused on compilation.
    ignoreDuringBuilds: true,
  },
};

export default nextConfig;
