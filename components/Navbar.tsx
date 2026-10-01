import { REPO_URL, SITE_NAME } from "@/lib/config";

export function Navbar() {
  return (
    <header>
      <nav className="nav container" aria-label="Ana menü">
        <a className="brand" href="#main">
          {SITE_NAME}
        </a>
        <ul className="nav-list">
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
    </header>
  );
}
