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

/**
 * Sitenin backend'in CORS izni olan ASIL adresi ve oraya yönlendirilen diğer adresler.
 *
 * Neden: backend yalnızca izin verdiği kökenden gelen isteklere yanıt verir (backend/main.py, `allowed_origins`;
 * şu an yalnızca verify-test-swart.vercel.app). Site Vercel'in başka bir adresinden (ör. verify-test-efee2.vercel.app)
 * açılırsa tarayıcı her isteği engeller ve kullanıcı "Sunucuya ulaşılamadı" görür. Bu adresler asıl adrese yönlendirilir.
 * Alan adı alınınca: alan adı backend'in `FRONTEND_ORIGIN` ayarına eklenmeli, sonra burası güncellenmeli.
 *
 * `verify-test-git-main-efee2`: yayın derlemesinin dal takma adı (11 Ekim denetiminde CORS hatası burada görüldü).
 * Her dağıtımın kendi adresi (verify-test-<kimlik>-efee2) bilerek yönlendirilmez: belirli bir dağıtımı incelemek
 * ve geri almak için gerekir. Diğer dalların önizlemelerinde backend adresi tanımlı değildir; form zaten kapalıdır.
 */
export const CANONICAL_HOST = "verify-test-swart.vercel.app";
export const REDIRECT_HOSTS = ["verify-test-efee2.vercel.app", "verify-test-git-main-efee2.vercel.app"];

const nextConfig: NextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  async headers() {
    return [{ source: "/:path*", headers: securityHeaders }];
  },
  async redirects() {
    // Geçici (307): alan adı alındığında asıl adres değişecek; tarayıcılar kalıcı olarak önbelleğe almasın.
    return REDIRECT_HOSTS.map((host) => ({
      source: "/:path*",
      has: [{ type: "host" as const, value: host }],
      destination: `https://${CANONICAL_HOST}/:path*`,
      permanent: false,
    }));
  },
};

export default nextConfig;
