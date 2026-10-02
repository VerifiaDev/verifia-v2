import type { NextConfig } from "next";

/**
 * Ek bağımlılık gerektirmeyen temel güvenlik başlıkları.
 * Content-Security-Policy bilerek YOK: Next.js'in satır içi betikleri için nonce düzeni gerekir ve
 * gerçek backend adresi `connect-src` içine yazılmalıdır; backend adresi kesinleşince eklenmeli.
 */
const securityHeaders = [
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  // Site başka sayfalara gömülmüyor. Gömülmesi istenirse bu satır (ve CSP frame-ancestors) güncellenmeli.
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
];

const nextConfig: NextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  async headers() {
    return [{ source: "/:path*", headers: securityHeaders }];
  },
};

export default nextConfig;
