import type { Metadata } from "next";
import { Analyzer } from "@/components/Analyzer";
import { Footer } from "@/components/Footer";
import { HowItWorks } from "@/components/HowItWorks";
import { Legend } from "@/components/Legend";
import { Navbar } from "@/components/Navbar";
import { TrustNotes } from "@/components/TrustNotes";
import { PrivacyNotes } from "@/components/PrivacyNotes";
import { apiInfo } from "@/lib/api";
import { jsonLdText, siteJsonLd } from "@/lib/seo";
import { SITE_ORIGIN } from "@/lib/site";

// Aynı içerik birden çok adresten sunulduğu için ana sayfa tek bir asıl adrese (canonical) işaret eder.
export const metadata: Metadata = SITE_ORIGIN ? { alternates: { canonical: "/" } } : {};

export default function HomePage() {
  return (
    <>
      {/* Arama motorları için yapılandırılmış veri; çalıştırılan bir betik değildir (içerik: lib/seo.ts). */}
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: jsonLdText(siteJsonLd()) }} />
      <Navbar />
      <main id="main">
        <div className="container layout">
          <div className="layout-main">
            <div className="hero">
              <h1 className="t-display">İddiaları kanıtlarla inceleyin</h1>
              {/* Bağlantıdan yalnızca servis destekliyorsa söz edilir (çalışmayan bir özellik vaat edilmez). */}
              <p className="hero-lead">
                {apiInfo.urlSupported
                  ? "Metin veya bağlantı ekleyin; kaynakları ve belirsizlikleri birlikte inceleyin."
                  : "Bir haber metni ya da iddia yapıştırın; kaynakları ve belirsizlikleri birlikte inceleyin."}
              </p>
            </div>
            <Analyzer />
          </div>

          {/* Geniş ekran: sonuç türleri yan sütunda sürekli görünür. */}
          <aside className="aside" aria-labelledby="legend-title">
            <h2 id="legend-title" className="legend-title">
              Sonuç türleri
            </h2>
            <Legend />
          </aside>
        </div>

        <HowItWorks />
        <TrustNotes />
        <PrivacyNotes />
      </main>
      <Footer />
    </>
  );
}
