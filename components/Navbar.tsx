import { SiteLinks } from "./SiteLinks";
import { SITE_NAME } from "@/lib/config";

export function Navbar() {
  return (
    <header>
      <nav className="nav container" aria-label="Ana menü">
        <a className="brand" href="#main">
          {SITE_NAME}
        </a>
        <SiteLinks className="nav-list" />
      </nav>
    </header>
  );
}
