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
              <p className="hero-eyebrow"><span aria-hidden="true" /> Haberi değil, kanıtı inceleyin</p>
              <h1 className="t-display">İddiaları kanıtlarla inceleyin</h1>
              {/* Bağlantıdan yalnızca servis destekliyorsa söz edilir (çalışmayan bir özellik vaat edilmez). */}
              <p className="hero-lead">
                {apiInfo.urlSupported
                  ? "Metin veya bağlantı ekleyin; kaynakları ve belirsizlikleri birlikte inceleyin."
                  : "Bir haber metni ya da iddia yapıştırın; kaynakları ve belirsizlikleri birlikte inceleyin."}
              </p>
              <div className="hero-points" aria-label="İncelemenin kapsamı">
                <span><i aria-hidden="true">01</i> İddialar tek tek incelenir</span>
                <span><i aria-hidden="true">02</i> Kaynaklar görünür kalır</span>
              </div>
            </div>
            <Analyzer />
          </div>

          {/* Geniş ekran: sonuç türleri yan sütunda sürekli görünür. */}
          <aside className="aside" aria-labelledby="legend-title">
            <div className="preview-card" aria-label="Apollo 11 örnek raporundan kısa önizleme">
              <div className="preview-card-head">
                <span className="preview-mark" aria-hidden="true"><span /></span>
                <div>
                  <p className="preview-overline">RAPOR ÖNİZLEMESİ</p>
                  <p className="preview-source">Apollo 11 · NASA kaynakları</p>
                </div>
                <span className="preview-index">02/03</span>
              </div>
              <p className="preview-claim">“Görevdeki üç astronot da Ay yüzeyinde yürüdü.”</p>
              <div className="preview-connector" aria-hidden="true"><span /></div>
              <div className="preview-evidence">
                <span className="preview-source-icon" aria-hidden="true">N</span>
                <span><strong>NASA · Apollo 11 Mission Overview</strong><small>Birincil kaynak · görev kaydı</small></span>
                <span className="preview-cite">[1]</span>
              </div>
              <div className="preview-verdict"><span aria-hidden="true">×</span><span><small>ÖN DEĞERLENDİRME</small><strong>Kanıtlar iddiayla çelişiyor</strong></span></div>
              <a className="preview-link" href="/ornek/apollo-11">Kaynaklı örneği incele <span aria-hidden="true">↗</span></a>
            </div>
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
