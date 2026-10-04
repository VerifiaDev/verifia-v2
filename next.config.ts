import type { NextConfig } from "next";

const isProduction = process.env.NODE_ENV === "production";

/** Backend adresinin kökü (örn. "https://api.ornek.com"); adres yoksa ya da bozuksa null. */
function apiOrigin(): string | null {
  const raw = process.env.NEXT_PUBLIC_API_BASE_URL;
  if (!raw) return null;
  try {
    return new URL(raw).origin;
  } catch {
    return null;
  }
}

/**
 * İçerik güvenlik politikası (CSP). Sayfa statik üretildiği için nonce kullanılamaz; Next.js'in ve tema
 * tercihinin satır içi betikleri `'unsafe-inline'` gerektirir (Next.js belgelerindeki "nonce'suz" kalıp).
 * Yine de politika şunları kısıtlar: betik/yazı tipi/görsel yalnızca siteden yüklenir, sayfa başka siteye
 * gömülemez ve — en önemlisi — sayfa yalnızca siteye ve tanımlı backend'e istek gönderebilir
 * (kullanıcının yapıştırdığı metin başka bir adrese gidemez).
 *
 * Backend adresi derleme sırasında `NEXT_PUBLIC_API_BASE_URL`'den okunur; adres değişince yeniden derlenir.
 * `upgrade-insecure-requests` bilerek yok: yerelde http ile çalışan bir backend'e bağlanmayı bozardı;
 * yayında site zaten HTTPS ve HSTS ile sunulur.
 * Geliştirmede Next.js'in anında yenileme düzeni `eval` ve WebSocket kullanır; yalnızca orada izin verilir.
 */
function contentSecurityPolicy(): string {
  const connect = ["'self'", apiOrigin(), isProduction ? null : "ws:"].filter(Boolean).join(" ");
  return [
    "default-src 'self'",
    `script-src 'self' 'unsafe-inline'${isProduction ? "" : " 'unsafe-eval'"}`,
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data: blob:",
    "font-src 'self'",
    `connect-src ${connect}`,
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
  ].join("; ");
}

/** Ek bağımlılık gerektirmeyen güvenlik başlıkları. */
const securityHeaders = [
  { key: "Content-Security-Policy", value: contentSecurityPolicy() },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  // Site başka sayfalara gömülmüyor. Gömülmesi istenirse bu satır ve CSP'deki frame-ancestors güncellenmeli.
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
