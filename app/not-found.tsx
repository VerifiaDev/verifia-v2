import type { Metadata } from "next";
import { PlainPage } from "@/components/PlainPage";
import { SITE_NAME } from "@/lib/config";

export const metadata: Metadata = {
  title: `Sayfa bulunamadı | ${SITE_NAME}`,
};

/** Sitede olmayan adresler için sayfa. */
export default function NotFound() {
  return (
    <PlainPage title="Sayfa bulunamadı">
      <p className="hero-lead">Bu adreste bir sayfa yok. Bağlantı eksik ya da yanlış yazılmış olabilir.</p>
      <p>
        <a className="btn" href="/">
          Ana sayfaya dön
        </a>
      </p>
    </PlainPage>
  );
}
