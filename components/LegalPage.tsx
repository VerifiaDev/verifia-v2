import type { ReactNode } from "react";
import { notFound } from "next/navigation";
import { PlainPage } from "./PlainPage";
import { LEGAL, LEGAL_COMPLETE, LEGAL_PAGES, joinNames, legalPagesHidden } from "@/lib/legal";
import { formatDate } from "@/lib/format";

/** Proje sahibinden gelecek bir bilgi. Boşsa uydurulmaz; eksik olduğu açıkça gösterilir. */
export function Fill({ value, label }: { value: string; label: string }) {
  return value.trim() ? <>{value}</> : <span className="legal-missing">[doldurulacak: {label}]</span>;
}

export function EmailLink() {
  return LEGAL.email.trim() ? <a href={`mailto:${LEGAL.email}`}>{LEGAL.email}</a> : <Fill value="" label="iletişim e-postası" />;
}

/** "verify ekibinin (Ad Soyad, Ad Soyad ve Ad Soyad)": "Bu site, … ticari olmayan bir projesidir." cümlesinde. */
export function Owner() {
  return (
    <>
      {LEGAL.owner}nin ({joinNames(LEGAL.members)})
    </>
  );
}

export function ExternalLink({ href, children }: { href: string; children: ReactNode }) {
  return (
    <a href={href} target="_blank" rel="noopener noreferrer">
      {children}
      <span className="sr-only"> (yeni sekmede açılır)</span>
    </a>
  );
}

/**
 * Üç yasal sayfanın ortak iskeleti: başlık, tarih, taslak uyarısı, içerik, diğer sayfalara bağlantılar.
 * Bilgiler eksikken yayındaki sitede sayfa 404 döner (bkz. lib/legal.ts).
 */
export function LegalPage({ title, path, children }: { title: string; path: string; children: ReactNode }) {
  if (legalPagesHidden()) notFound();
  return (
    <PlainPage title={title}>
      {!LEGAL_COMPLETE && (
        <p className="note note--warn" role="note">
          <strong className="note-label">Taslak</strong>
          <span>Bu sayfa henüz tamamlanmadı; köşeli parantez içindeki bilgiler eklenmeden yayına alınmayacak.</span>
        </p>
      )}
      <p className="muted t-meta">
        Son güncelleme: <time dateTime={LEGAL.updated}>{formatDate(LEGAL.updated)}</time>
      </p>
      <div className="legal">{children}</div>
      <nav className="legal-nav" aria-label="Yasal sayfalar">
        {LEGAL_PAGES.filter((p) => p.path !== path).map((p) => (
          <a key={p.path} href={p.path}>
            {p.label}
          </a>
        ))}
        <a href="/">Ana sayfaya dön</a>
      </nav>
    </PlainPage>
  );
}
