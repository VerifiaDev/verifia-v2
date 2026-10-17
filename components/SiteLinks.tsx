import { REPO_URL, SITE_LINKS } from "@/lib/config";

/** Navbar ve footer'da ortak kullanılan bağlantı listesi. Stil `className` ile verilir. */
export function SiteLinks({ className }: { className: string }) {
  return (
    <ul className={className}>
      {SITE_LINKS.map((l) => (
        <li key={l.href}>
          <a href={l.href}>{l.label}</a>
        </li>
      ))}
      {REPO_URL && (
        <li>
          <a href={REPO_URL} target="_blank" rel="noopener noreferrer">
            GitHub<span className="sr-only"> (yeni sekmede açılır)</span>
          </a>
        </li>
      )}
    </ul>
  );
}
