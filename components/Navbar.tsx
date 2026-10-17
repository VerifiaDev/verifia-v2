import { Brand } from "./Brand";
import { SiteLinks } from "./SiteLinks";
import { ThemeToggle } from "./ThemeToggle";

/** Üst bant: marka (bkz. Brand), sayfa içi menü ve gece modu düğmesi. */
export function Navbar() {
  return (
    <header>
      <div className="masthead container">
        <Brand href="#main" tagline />
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
