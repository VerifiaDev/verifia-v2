"use client";

import { useEffect, useRef } from "react";
import { ClaimItem } from "./ClaimItem";
import { ClaimList } from "./ClaimList";
import type { CheckResult } from "@/lib/types";

interface Props {
  result: CheckResult;
  input: string;
  onReset: () => void;
}

export function ResultView({ result, input, onReset }: Props) {
  const headingRef = useRef<HTMLHeadingElement>(null);
  const { claims, unverifiable } = result;

  // Sonuç gelince odağı başlığa taşı: ekran okuyucu kullanıcı sonucu duysun.
  useEffect(() => {
    headingRef.current?.focus();
  }, []);

  return (
    <section aria-labelledby="result-title" className="result">
      <div className="result-head">
        <h2 id="result-title" ref={headingRef} tabIndex={-1} className="t-h2 result-title">
          {claims.length === 0 ? "Doğrulanabilir iddia bulunamadı" : `${claims.length} iddia incelendi`}
        </h2>

        <details className="input-echo">
          <summary>Gönderdiğiniz içerik</summary>
          <p>{input}</p>
        </details>

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
            <ClaimItem key={c.id} claim={c} index={i} total={claims.length} />
          ))}
        </div>
      )}

      {unverifiable.length > 0 && (
        <section className="unverifiable" aria-labelledby="unverifiable-title">
          <h3 id="unverifiable-title" className="t-h4">
            Doğrulanmayan ifadeler ({unverifiable.length})
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
        <p className="muted t-meta">
          Bu sonuç otomatik bir ön değerlendirmedir. Karar vermeden önce yukarıdaki kaynakları kendiniz de kontrol edin.
        </p>
        <button type="button" className="btn btn-quiet" onClick={onReset}>
          Yeni bir içerik doğrula
        </button>
      </div>
    </section>
  );
}
