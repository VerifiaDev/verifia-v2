import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";
import { SITE_NAME, SITE_TAGLINE } from "@/lib/config";
import "./globals.css";

export const metadata: Metadata = {
  title: `${SITE_NAME} — iddiaları kaynaklarıyla doğrulayın`,
  description: `${SITE_TAGLINE} Bir metni yapıştırın; iddiaları ve dayandığı kaynakları görün.`,
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="tr">
      <body>
        <a className="skip-link" href="#main">
          İçeriğe geç
        </a>
        {children}
      </body>
    </html>
  );
}
