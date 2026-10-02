import { SiteLinks } from "./SiteLinks";
import { SITE_NAME } from "@/lib/config";

function BrandMark() {
  return (
    <svg className="brand-mark" viewBox="0 0 36 36" aria-hidden="true" focusable="false">
      <path d="M11 8.5h10l5 5v14H11z" />
      <path d="M21 8.5v5h5M15 18h7M15 22h5" />
      <circle cx="25" cy="25" r="3.25" />
    </svg>
  );
}

export function Navbar() {
  return (
    <header>
      <nav className="nav container" aria-label="Ana menü">
        <a className="brand" href="#main">
          <BrandMark />
          <span>{SITE_NAME}</span>
        </a>
        <SiteLinks className="nav-list" />
      </nav>
    </header>
  );
}
