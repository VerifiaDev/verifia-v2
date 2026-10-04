import { SITE_NAME, SITE_TAGLINE } from "@/lib/config";

interface Props {
  /** Verilirse ad bağlantı olur (üst bant). Verilmezse düz yazıdır (alt bilgi). */
  href?: string;
  /** Küçük boy: alt bilgi. */
  small?: boolean;
  /** Slogan adın yanında gösterilsin mi (üst bant). */
  tagline?: boolean;
}

/**
 * Marka tek yerde: logo yalnızca yazıdır (sözcük işareti), ad başlık yazı tipiyle yazılır.
 * Ad ve slogan `lib/config.ts` içinden gelir; marka değişirse bu dosya ile o iki sabit yeter.
 * (Paylaşım görseli ve simgeler ayrı dosyalardır: `app/opengraph-image.png`, `app/icon.svg`.)
 */
export function Brand({ href, small = false, tagline = false }: Props) {
  const className = small ? "brand brand--small" : "brand";
  const name = href ? (
    <a className={className} href={href}>
      {SITE_NAME}
    </a>
  ) : (
    <span className={className}>{SITE_NAME}</span>
  );
  if (!tagline) return name;
  return (
    <div className="masthead-brand">
      {name}
      <p className="brand-tagline">{SITE_TAGLINE}</p>
    </div>
  );
}
