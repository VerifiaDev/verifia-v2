import { Analyzer } from "@/components/Analyzer";
import { Footer } from "@/components/Footer";
import { HowItWorks } from "@/components/HowItWorks";
import { Navbar } from "@/components/Navbar";
import { TrustNotes } from "@/components/TrustNotes";
import { VerdictSummary } from "@/components/VerdictSummary";
import { VERDICT_META, VERDICT_ORDER } from "@/lib/format";

export default function HomePage() {
  return (
    <>
      <Navbar />
      <main id="main">
        <div className="container hero">
          <p className="hero-kicker">Kaynak temelli iddia incelemesi</p>
          <h1 className="t-display">İddiaları kanıtlarla inceleyin</h1>
          <p className="hero-lead">
            Metin veya bağlantı ekleyin; kaynakları ve belirsizlikleri birlikte inceleyin.
          </p>
        </div>

        <div className="container layout">
          <div className="layout-main">
            <Analyzer />
          </div>
          <aside className="aside" aria-labelledby="legend-title">
            <h2 id="legend-title" className="t-h4 legend-title">
              Sonuçlar ne anlama gelir?
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
          </aside>
        </div>

        <HowItWorks />
        <TrustNotes />
      </main>
      <Footer />
    </>
  );
}
