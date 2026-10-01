import { SiteLinks } from "./SiteLinks";
import { SITE_NAME, SITE_TAGLINE } from "@/lib/config";

export function Footer() {
  return (
    <footer className="site-footer">
      <div className="container footer-row">
        <p>
          <strong>{SITE_NAME}</strong> — {SITE_TAGLINE} Sonuçlar otomatik üretilir ve hata içerebilir; son karar her
          zaman sizindir.
        </p>
        <nav aria-label="Alt menü">
          <SiteLinks className="footer-links" />
        </nav>
      </div>
    </footer>
  );
}
