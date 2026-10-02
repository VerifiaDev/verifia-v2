import type { Metadata, Viewport } from "next";
import localFont from "next/font/local";
import type { ReactNode } from "react";
import { SITE_NAME, SITE_TAGLINE } from "@/lib/config";
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

const TITLE = `${SITE_NAME} — kanıt temelli iddia incelemesi`;
const DESCRIPTION = `${SITE_TAGLINE} Bir metin ya da haber bağlantısı ekleyin; iddiaları ve ilgili kaynakları birlikte inceleyin.`;

// Not: canonical/metadataBase ve paylaşım görseli (og:image) için yayın adresi gerekir; adres kesinleşince eklenir.
export const metadata: Metadata = {
  title: TITLE,
  description: DESCRIPTION,
  openGraph: { title: TITLE, description: DESCRIPTION, type: "website", locale: "tr_TR", siteName: SITE_NAME },
  twitter: { card: "summary", title: TITLE, description: DESCRIPTION },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="tr" className={`${fontSerif.variable} ${fontSans.variable}`}>
      <body>
        <a className="skip-link" href="#main">
          İçeriğe geç
        </a>
        {children}
      </body>
    </html>
  );
}
