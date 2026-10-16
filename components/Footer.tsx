import { Brand } from "./Brand";
import { SiteLinks } from "./SiteLinks";
import { SITE_TAGLINE } from "@/lib/config";
import { LEGAL, LEGAL_COMPLETE, LEGAL_PAGES, joinNames } from "@/lib/legal";

/**
 * Alt bilgi: kısa tanım, hizmeti sunanlar (işletme bilgisi) ve bağlantılar.
 * Yasal sayfalar, bilgileri tamamlanıp yayına girince listelenir (bkz. lib/legal.ts); o zamana kadar ana
 * sayfadaki "İçeriğiniz ve gizlilik" bölümüne bağlanılır.
 */
export function Footer() {
  return (
    <footer className="site-footer">
      <div className="container footer-row">
        <div className="footer-about">
          <Brand small />
          <p>
            {SITE_TAGLINE} Sonuçlar otomatik bir ön değerlendirmedir; önemli kararlar için kaynakları kendiniz de
            inceleyin.
          </p>
          <p>
            Bu site, {LEGAL.owner}nin ({joinNames(LEGAL.members)}) ticari olmayan bir projesidir.
            {LEGAL.email.trim() && (
              <>
                {" "}
                İletişim: <a href={`mailto:${LEGAL.email}`}>{LEGAL.email}</a>
              </>
            )}
          </p>
        </div>
        <nav aria-label="Alt menü">
          <SiteLinks className="footer-links" />
          <ul className="footer-links">
            {LEGAL_COMPLETE ? (
              LEGAL_PAGES.map((p) => (
                <li key={p.path}>
                  <a href={p.path}>{p.label}</a>
                </li>
              ))
            ) : (
              <li>
                <a href="#gizlilik">İçeriğiniz ve gizlilik</a>
              </li>
            )}
          </ul>
        </nav>
      </div>
    </footer>
  );
}
