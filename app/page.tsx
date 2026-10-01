import { Analyzer } from "@/components/Analyzer";
import { Footer } from "@/components/Footer";
import { HowItWorks } from "@/components/HowItWorks";
import { Navbar } from "@/components/Navbar";
import { TrustNotes } from "@/components/TrustNotes";
import { VERDICT_META, VERDICT_ORDER } from "@/lib/format";

export default function HomePage() {
  return (
    <>
      <Navbar />
      <main id="main">
        <div className="container hero">
          <h1 className="t-display">Şüpheli içeriği kanıtlarla doğrulayın</h1>
          <p className="hero-lead">
            Bir metin ya da haber bağlantısı gönderin. İçindeki iddiaları ayrı ayrı inceler, hangi kaynağın ne dediğini
            gösteririz. Karar sizin.
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
                  <dt className={`tone-${VERDICT_META[v].tone}`}>
                    <span aria-hidden="true">{VERDICT_META[v].symbol} </span>
                    <strong>{VERDICT_META[v].label}</strong>
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
