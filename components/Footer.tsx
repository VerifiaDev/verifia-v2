import { REPO_URL, SITE_NAME, SITE_TAGLINE } from "@/lib/config";

export function Footer() {
  return (
    <footer className="site-footer">
      <div className="container footer-row">
        <p>
          <strong>{SITE_NAME}</strong> — {SITE_TAGLINE} Sonuçlar otomatik üretilir ve hata içerebilir; son karar her
          zaman sizindir.
        </p>
        <nav aria-label="Alt menü">
          <ul className="footer-links">
            <li>
              <a href="#nasil">Nasıl çalışır?</a>
            </li>
            <li>
              <a href="#guven">Güven ilkeleri</a>
            </li>
            {REPO_URL && (
              <li>
                <a href={REPO_URL} target="_blank" rel="noopener noreferrer">
                  GitHub<span className="sr-only"> (yeni sekmede açılır)</span>
                </a>
              </li>
            )}
          </ul>
        </nav>
      </div>
    </footer>
  );
}
