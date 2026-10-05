"use client";

import { useEffect, useRef } from "react";
import { ClaimItem } from "./ClaimItem";
import { ClaimList } from "./ClaimList";
import type { CheckResult } from "@/lib/types";

interface Props {
  result: CheckResult;
  onReset: () => void;
  /** Örnek (mock) veri modunda true: her iddiada "örnek veri" etiketi gösterilir. */
  sample?: boolean;
  /** Sabit örnek sonuç (servis bağlı değilken): başlık, not ve kapatma düğmesi buna göre değişir. */
  showcase?: boolean;
}

/**
 * Sonuç, giriş kartının dışında kendi bölümünde durur (kartın içinde uzun, dar bir sütuna sıkışmasın diye).
 * Gönderilen içerik burada yinelenmez: yukarıdaki kartta özet olarak durur.
 */
export function ResultView({ result, onReset, sample = false, showcase = false }: Props) {
  const headingRef = useRef<HTMLHeadingElement>(null);
  const { claims, unverifiable, unreadable } = result;

  // Sonuç gelince odağı başlığa taşı: ekran okuyucu kullanıcı sonucu duysun.
  useEffect(() => {
    headingRef.current?.focus();
  }, []);

  return (
    <section aria-labelledby="result-title" className="result">
      <div className="result-head">
        <p className="result-kicker">{showcase ? "Örnek inceleme" : "İnceleme sonucu"}</p>
        <h2 id="result-title" ref={headingRef} tabIndex={-1} className="t-h2 result-title">
          {claims.length === 0 ? "İncelenebilir iddia bulunamadı" : `${claims.length} iddia incelendi`}
        </h2>

        {showcase && (
          <p className="note note--warn" role="note">
            <strong className="note-label">Örnek</strong>
            <span>
              Bu sonuç, servis bağlanana kadar arayüzü göstermek için hazırlanmış sabit bir örnektir. İddialar ve
              kaynaklar uydurmadır.
            </span>
          </p>
        )}

        {/* Eksik sonuç başta söylenir: uzun bir sayfanın sonundaki liste gözden kaçabilir. */}
        {unreadable.length > 0 && (
          <p className="note note--warn" role="note">
            <strong className="note-label">Eksik</strong>
            <span>
              {unreadable.length} iddianın sonucu okunamadı; bu iddialar aşağıda ayrıca listelenir.
            </span>
          </p>
        )}

        {claims.length > 1 && <ClaimList claims={claims} />}
      </div>

      {claims.length === 0 ? (
        <div className="state">
          <p>Gönderdiğiniz içerikte kaynaklarla kontrol edilebilecek somut bir iddia bulunamadı.</p>
          <p className="muted">Tarih, sayı, kişi ya da olay içeren bir cümleyle yeniden deneyin.</p>
        </div>
      ) : (
        <div className="claims">
          {claims.map((c, i) => (
            <ClaimItem key={c.id} claim={c} index={i} total={claims.length} sample={sample} showcase={showcase} />
          ))}
        </div>
      )}

      {unreadable.length > 0 && (
        <section className="unverifiable" aria-labelledby="unreadable-title">
          <h3 id="unreadable-title" className="t-h4">
            Sonucu gösterilemeyen iddialar ({unreadable.length})
          </h3>
          <p className="muted t-meta">
            Servisten gelen sonuç tanınmadı. Bu, iddiaların doğru ya da yanlış olduğu anlamına gelmez; yeniden
            deneyebilirsiniz.
          </p>
          <ul>
            {unreadable.map((t, i) => (
              <li key={i}>{t}</li>
            ))}
          </ul>
        </section>
      )}

      {unverifiable.length > 0 && (
        <section className="unverifiable" aria-labelledby="unverifiable-title">
          <h3 id="unverifiable-title" className="t-h4">
            İncelenmeyen ifadeler ({unverifiable.length})
          </h3>
          <p className="muted t-meta">Görüş, tahmin ya da ölçülemeyen ifadeler kaynaklarla kontrol edilemez.</p>
          <ul>
            {unverifiable.map((t, i) => (
              <li key={i}>{t}</li>
            ))}
          </ul>
        </section>
      )}

      <div className="result-foot">
        {!showcase && (
          <p className="muted t-meta">
            Bu sonuç otomatik bir ön değerlendirmedir. Karar vermeden önce yukarıdaki kaynakları kendiniz de kontrol
            edin.
          </p>
        )}
        <button type="button" className="btn btn-quiet" onClick={onReset}>
          {showcase ? "Örneği kapat" : "Yeni bir içerik incele"}
        </button>
      </div>
    </section>
  );
}
