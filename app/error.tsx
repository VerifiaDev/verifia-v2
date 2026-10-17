"use client"; // Hata sınırları istemci bileşeni olmak zorundadır.

import { useEffect } from "react";
import { PlainPage } from "@/components/PlainPage";

/**
 * Sayfa çizilirken beklenmeyen bir hata olursa gösterilir (Next.js'in İngilizce varsayılan ekranı yerine).
 * Teknik ayrıntı kullanıcıya gösterilmez; geliştirici için konsola yazılır.
 */
export default function ErrorPage({ error, retry }: { error: Error & { digest?: string }; retry: () => void }) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <PlainPage title="Sayfa görüntülenemedi">
      <p className="hero-lead">
        Sayfa çizilirken beklenmeyen bir hata oluştu. Yeniden denediğinizde yazdığınız içerik alanda kalmayabilir.
      </p>
      <div className="actions">
        <button type="button" className="btn" onClick={() => retry()}>
          Yeniden dene
        </button>
        {/* Full document navigation intentionally clears the failed client router. */}
        {/* eslint-disable-next-line @next/next/no-html-link-for-pages */}
        <a className="btn btn-quiet" href="/">
          Ana sayfaya dön
        </a>
      </div>
    </PlainPage>
  );
}
