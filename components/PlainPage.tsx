import type { ReactNode } from "react";
import { Brand } from "./Brand";

/**
 * Ana sayfa dışındaki iki durum için sade iskelet: bulunamayan adres (app/not-found.tsx) ve
 * beklenmeyen hata (app/error.tsx). Kök düzenin içinde çizilir; "İçeriğe geç" bağlantısının hedefi (`#main`) burada da vardır.
 * Ana menü bilerek yok: bağlantıları sayfa içi (#…) olduğu için bu sayfalarda hiçbir yere gitmez.
 * Logo düz bağlantıdır (tam sayfa yüklemesi): hata sonrasında sayfa temiz bir durumla açılsın.
 */
export function PlainPage({ title, children }: { title: string; children: ReactNode }) {
  return (
    <>
      <header>
        <div className="masthead container">
          <Brand href="/" tagline />
        </div>
      </header>
      <main id="main">
        <div className="container plain-page">
          <h1 className="t-display">{title}</h1>
          {children}
        </div>
      </main>
    </>
  );
}
