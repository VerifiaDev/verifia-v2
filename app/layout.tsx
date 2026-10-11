import type { Metadata, Viewport } from "next";
import localFont from "next/font/local";
import type { ReactNode } from "react";
import { SITE_NAME, SITE_TAGLINE } from "@/lib/config";
import { SITE_ORIGIN } from "@/lib/site";
import "./globals.css";

/**
 * Yazı tipleri proje içinden sunulur (app/fonts): dış isteğe gerek yok, her cihazda aynı görünür.
 * Dosyalar Latin + Türkçe harflerle sınırlandırılmış değişken (400–700) yazı tipleridir; lisans: SIL OFL (aynı klasörde).
 * Başlık ve alıntılar Literata, arayüz ve gövde Atkinson Hyperlegible Next. Yığınlar globals.css içinde.
 */
const fontSerif = localFont({
  src: "./fonts/Literata-tr.woff2",
  weight: "400 700",
  style: "normal",
  display: "swap",
  variable: "--font-serif",
  adjustFontFallback: "Times New Roman",
});
const fontSans = localFont({
  src: "./fonts/AtkinsonHyperlegibleNext-tr.woff2",
  weight: "400 700",
  style: "normal",
  display: "swap",
  variable: "--font-sans",
  adjustFontFallback: "Arial",
});

const TITLE = `${SITE_NAME} | Kanıt temelli iddia incelemesi`;
const DESCRIPTION = `${SITE_TAGLINE} Bir haber metni ya da iddia ekleyin; iddiaları ve ilgili kaynakları birlikte inceleyin.`;

// Paylaşım görseli: app/opengraph-image.png ve app/twitter-image.png (dosya adı kuralıyla kendiliğinden eklenir).
// Yayın adresi (metadataBase) için bkz. lib/site.ts. Canonical yalnızca ana sayfada yazılır (app/page.tsx).
export const metadata: Metadata = {
  ...(SITE_ORIGIN ? { metadataBase: new URL(SITE_ORIGIN) } : {}),
  title: TITLE,
  description: DESCRIPTION,
  openGraph: {
    title: TITLE,
    description: DESCRIPTION,
    type: "website",
    locale: "tr_TR",
    siteName: SITE_NAME,
    ...(SITE_ORIGIN ? { url: "/" } : {}),
  },
  twitter: { card: "summary_large_image", title: TITLE, description: DESCRIPTION },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  colorScheme: "light dark",
  /** Telefon tarayıcısının üst çubuğu temayla aynı renkte olsun (değerler globals.css'teki --paper). Elle seçimde ThemeToggle günceller. */
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#f6f7f5" },
    { media: "(prefers-color-scheme: dark)", color: "#11151a" },
  ],
};

/** Kayıtlı gece/gündüz tercihini ilk boyamadan önce uygular (yanıp sönmeyi önler). Anahtar: components/ThemeToggle.tsx */
const THEME_SCRIPT = `try{var t=localStorage.getItem("verify-theme");if(t==="dark"||t==="light"){document.documentElement.dataset.theme=t;var c=t==="dark"?"#11151a":"#f6f7f5";document.querySelectorAll('meta[name="theme-color"]').forEach(function(m){m.removeAttribute("media");m.setAttribute("content",c)})}}catch(e){}`;

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="tr" className={`${fontSerif.variable} ${fontSans.variable}`} suppressHydrationWarning>
      <body>
        <script dangerouslySetInnerHTML={{ __html: THEME_SCRIPT }} />
        <a className="skip-link" href="#main">
          İçeriğe geç
        </a>
        {children}
      </body>
    </html>
  );
}
