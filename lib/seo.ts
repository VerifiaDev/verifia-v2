import { SAMPLE_REPORT_PATH, SITE_NAME, SITE_TAGLINE } from "./config";
import { SITE_ORIGIN } from "./site";
import { LEGAL_COMPLETE, LEGAL_PAGES } from "./legal";

/**
 * Arama motorları için robots.txt, site haritası ve yapılandırılmış veri (app/robots.ts, app/sitemap.ts, app/page.tsx).
 * Yayın adresi derleme sırasında bilinir (lib/site.ts). Bilinmiyorsa (yerel derleme) adres uydurulmaz:
 * robots dosyasında site haritası satırı olmaz, site haritası boş kalır.
 */

/** Site haritasına giren sayfalar. Yeni bir sayfa eklenince buraya da eklenir; arama motoruna kapalı sayfalar eklenmez. */
const INDEXED_PATHS = ["/", SAMPLE_REPORT_PATH, ...(LEGAL_COMPLETE ? LEGAL_PAGES.map((p) => p.path) : [])];

export function robotsRules(origin: string | null = SITE_ORIGIN): { rules: { userAgent: string; allow: string }; sitemap?: string } {
  return { rules: { userAgent: "*", allow: "/" }, ...(origin ? { sitemap: `${origin}/sitemap.xml` } : {}) };
}

export function sitemapEntries(origin: string | null = SITE_ORIGIN): { url: string }[] {
  return origin ? INDEXED_PATHS.map((path) => ({ url: `${origin}${path}` })) : [];
}

/** schema.org tanımı: yalnızca doğrulanabilir bilgiler (ad, adres, dil, açıklama). Puan, yorum ya da fiyat uydurulmaz. */
export function siteJsonLd(origin: string | null = SITE_ORIGIN): Record<string, string> {
  return {
    "@context": "https://schema.org",
    "@type": "WebApplication",
    name: SITE_NAME,
    description: `${SITE_TAGLINE} Bir haber metni ya da iddia ekleyin; iddiaları ve ilgili kaynakları birlikte inceleyin.`,
    inLanguage: "tr",
    applicationCategory: "ReferenceApplication",
    ...(origin ? { url: `${origin}/` } : {}),
  };
}

/** <script type="application/ld+json"> içine yazılacak metin. "<" kaçırılır: içerik etiketi kapatamaz (Next.js belgelerindeki kalıp). */
export function jsonLdText(data: unknown): string {
  return JSON.stringify(data).replace(/</g, "\\u003c");
}
