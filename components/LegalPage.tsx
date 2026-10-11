import type { ReactNode } from "react";
import { PlainPage } from "./PlainPage";
import { LEGAL, LEGAL_COMPLETE, PRIVACY_PATH, TERMS_PATH } from "@/lib/legal";
import { formatDate } from "@/lib/format";

/** Proje sahibinden gelecek bir bilgi. Boşsa uydurulmaz; eksik olduğu açıkça gösterilir. */
export function Fill({ value, label }: { value: string; label: string }) {
  return value.trim() ? <>{value}</> : <span className="legal-missing">[doldurulacak: {label}]</span>;
}

export function EmailLink() {
  return LEGAL.email.trim() ? <a href={`mailto:${LEGAL.email}`}>{LEGAL.email}</a> : <Fill value="" label="iletişim e-postası" />;
}

/** Gizlilik politikası ve kullanım koşulları için ortak iskelet: başlık, tarih, taslak uyarısı, içerik, karşı bağlantı. */
export function LegalPage({ title, other, children }: { title: string; other: "privacy" | "terms"; children: ReactNode }) {
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
      <p className="legal-nav">
        {other === "privacy" ? <a href={PRIVACY_PATH}>Gizlilik politikası</a> : <a href={TERMS_PATH}>Kullanım koşulları</a>}
        <a href="/">Ana sayfaya dön</a>
      </p>
    </PlainPage>
  );
}
