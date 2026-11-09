/** @type {import('next').NextConfig} */
const nextConfig = {
  // Desactivar ESLint durante build para deploy rápido
  eslint: { ignoreDuringBuilds: true },
  typescript: { ignoreBuildErrors: false },
};

export default nextConfig;
