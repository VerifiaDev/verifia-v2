import type { Metadata } from "next";
import Link from "next/link";
import { Brand } from "@/components/Brand";
import { Legend } from "@/components/Legend";
import { SampleReport } from "@/components/SampleReport";
import { SAMPLE_REPORT_PATH, SITE_NAME } from "@/lib/config";
import { SITE_ORIGIN } from "@/lib/site";

export const metadata: Metadata = {
  title: `Apollo 11 örnek raporu | ${SITE_NAME}`,
  description: "Önceden hazırlanmış örnek inceleme: bir metin, üç iddia ve NASA kaynakları. Canlı analiz değildir.",
  ...(SITE_ORIGIN ? { alternates: { canonical: SAMPLE_REPORT_PATH } } : {}),
};

/**
 * Hazır örnek raporun paylaşılabilir sayfası. Ana sayfadaki `?example=apollo-11` yalnızca tarayıcıda açılıyordu;
 * bağlantı önizlemeleri ve JavaScript'siz okuyucular raporu göremiyordu. Bu sayfa derlemede statik üretilir.
 * Üst bantta ana menü bilerek yok: bağlantıları ana sayfanın bölümlerine gider (bkz. components/PlainPage.tsx).
 * Düzen ana sayfadaki sonuç görünümüyle aynıdır (geniş ekranda sonuç türleri yan sütunda).
 */
export default function SampleReportPage() {
  return (
    <>
      <header>
        <div className="masthead container">
          <Brand href="/" tagline />
        </div>
      </header>
      <main id="main">
        <div className="container layout">
          <div className="layout-main">
            <div className="hero">
              <h1 className="t-display">Örnek rapor</h1>
              <p className="hero-lead">
                Bir incelemenin nasıl göründüğünü gösteren hazır örnek. <Link href="/">Kendi metninizi inceleyin</Link>
              </p>
            </div>
            <SampleReport />
          </div>
          <aside className="aside" aria-labelledby="legend-title">
            <h2 id="legend-title" className="legend-title">
              Sonuç türleri
            </h2>
            <Legend />
          </aside>
        </div>
      </main>
    </>
  );
}
