import type { Metadata } from "next";
import Link from "next/link";
import { SITE_NAME, SITE_TAGLINE } from "@/lib/config";

export const metadata: Metadata = {
  title: `Sayfa bulunamadı — ${SITE_NAME}`,
};

/**
 * Sitede olmayan adresler için sayfa. Kök düzenin içinde çizilir: dil, yazı tipi, tema ve
 * "İçeriğe geç" bağlantısı (hedefi `#main`) burada da çalışır.
 * Ana menü bilerek yok: bağlantıları sayfa içi (#…) olduğu için bu adreste hiçbir yere gitmez.
 */
export default function NotFound() {
  return (
    <>
      <header>
        <div className="masthead container">
          <div className="masthead-brand">
            <Link className="brand" href="/">
              {SITE_NAME}
            </Link>
            <p className="brand-tagline">{SITE_TAGLINE}</p>
          </div>
        </div>
      </header>
      <main id="main">
        <div className="container not-found">
          <h1 className="t-display">Sayfa bulunamadı</h1>
          <p className="hero-lead">Bu adreste bir sayfa yok. Bağlantı eksik ya da yanlış yazılmış olabilir.</p>
          <p>
            <Link className="btn" href="/">
              Ana sayfaya dön
            </Link>
          </p>
        </div>
      </main>
    </>
  );
}
