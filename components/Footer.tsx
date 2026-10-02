import { SiteLinks } from "./SiteLinks";
import { SITE_NAME, SITE_TAGLINE } from "@/lib/config";

export function Footer() {
  return (
    <footer className="site-footer">
      <div className="container footer-row">
        <p>
          <strong>{SITE_NAME}</strong> — {SITE_TAGLINE} Sonuçlar otomatik bir ön değerlendirmedir; önemli kararlar için kaynakları kendiniz de inceleyin.
        </p>
        <nav aria-label="Alt menü">
          <SiteLinks className="footer-links" />
        </nav>
      </div>
    </footer>
  );
}
