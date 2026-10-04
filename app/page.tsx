import { Analyzer } from "@/components/Analyzer";
import { Footer } from "@/components/Footer";
import { HowItWorks } from "@/components/HowItWorks";
import { Navbar } from "@/components/Navbar";
import { TrustNotes } from "@/components/TrustNotes";
import { VerdictSummary } from "@/components/VerdictSummary";
import { VERDICT_META, VERDICT_ORDER } from "@/lib/format";
import { SITE_ORIGIN } from "@/lib/site";
import type { Metadata } from "next";

// Aynı içerik birden çok adresten sunulduğu için ana sayfa tek bir asıl adrese (canonical) işaret eder.
export const metadata: Metadata = SITE_ORIGIN ? { alternates: { canonical: "/" } } : {};

export default function HomePage() {
  return (
    <>
      <Navbar />
      <main id="main">
        <div className="container layout">
          <div className="layout-main">
            <div className="hero">
              <h1 className="t-display">İddiaları kanıtlarla inceleyin</h1>
              <p className="hero-lead">
                Metin veya bağlantı ekleyin; kaynakları ve belirsizlikleri birlikte inceleyin.
              </p>
            </div>
            <Analyzer />
          </div>
          <aside className="aside" aria-labelledby="legend-title">
            <h2 id="legend-title" className="legend-title">
              Sonuç türleri
            </h2>
            <dl className="legend">
              {VERDICT_ORDER.map((v) => (
                <div key={v}>
                  {/* Sonuçlardaki halkalı simgenin aynısı: açıklama ile sonuç aynı görünsün. */}
                  <dt>
                    <VerdictSummary verdict={v} variant="inline" />
                  </dt>
                  <dd>{VERDICT_META[v].meaning}</dd>
                </div>
              ))}
            </dl>
            <p className="legend-note">
              Bir sonuç kesin hüküm değildir. Kaynağı, bağlamı ve kanıtın sınırlarını birlikte okuyun.
            </p>
          </aside>
        </div>

        <HowItWorks />
        <TrustNotes />
      </main>
      <Footer />
    </>
  );
}
