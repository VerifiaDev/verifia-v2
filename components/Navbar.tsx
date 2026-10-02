import { SiteLinks } from "./SiteLinks";
import { ThemeToggle } from "./ThemeToggle";
import { SITE_NAME, SITE_TAGLINE } from "@/lib/config";

/** Logo yalnızca yazıdır (sözcük işareti): simge yok, ad başlık yazı tipiyle yazılır. */
export function Navbar() {
  return (
    <header>
      <div className="masthead container">
        <div className="masthead-brand">
          <a className="brand" href="#main">
            {SITE_NAME}
          </a>
          <p className="brand-tagline">{SITE_TAGLINE}</p>
        </div>
        <div className="masthead-end">
          <nav aria-label="Ana menü">
            <SiteLinks className="nav-list" />
          </nav>
          <ThemeToggle />
        </div>
      </div>
    </header>
  );
}
