import { Brand } from "./Brand";
import { SiteLinks } from "./SiteLinks";
import { SITE_TAGLINE } from "@/lib/config";

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
        </div>
        <nav aria-label="Alt menü">
          <SiteLinks className="footer-links" />
        </nav>
      </div>
    </footer>
  );
}
