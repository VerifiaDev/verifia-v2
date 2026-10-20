"use client";

import { useEffect, useRef, useState } from "react";
import { ERROR_COPY } from "@/lib/format";
import type { ApiError } from "@/lib/types";

interface Props {
  error: ApiError;
  onRetry: () => void;
  onEdit: () => void;
}

/** Zaman aşımından sonra sunucu önceki isteği hâlâ işliyor olabilir; hemen yeniden göndermek "meşgul" cevabı getirir. */
const TIMEOUT_COOLDOWN_S = 8;

/**
 * Hata: ne oldu → şimdi ne yapabilirsiniz. Teknik ayrıntı kullanıcıya gösterilmez.
 * Duyuru odakla yapılır: odak başlığa taşınır ve ekran okuyucu başlığı okur. Kapsayıcıda ayrıca
 * `role="alert"` yok; olsaydı panelin tamamı (liste ve düğmeler dahil) bir kez de canlı bölge olarak okunurdu.
 */
export function ErrorState({ error, onRetry, onEdit }: Props) {
  const copy = ERROR_COPY[error.code] ?? ERROR_COPY.INTERNAL_ERROR;
  const headingRef = useRef<HTMLHeadingElement>(null);
  // Sunucu `Retry-After` verdiyse o süre, zaman aşımında kısa bir bekleme; süre dolana kadar "Yeniden dene" kapalı.
  const wait = error.retryAfterSeconds ?? (error.code === "TIMEOUT" ? TIMEOUT_COOLDOWN_S : 0);
  const [left, setLeft] = useState(wait);
  useEffect(() => {
    if (left <= 0) return;
    const t = setTimeout(() => setLeft((n) => n - 1), 1000);
    return () => clearTimeout(t);
  }, [left]);

  // Hata görünür alanın dışında (örn. telefonda formun altında) kalabilir ve gönder düğmesi devre dışı
  // kalınca odak sayfa başına düşer. Odağı başlığa taşımak hem görünür alana getirir hem de odağı korur.
  useEffect(() => {
    headingRef.current?.focus();
  }, []);

  return (
    <div className="error-state">
      <h2 ref={headingRef} tabIndex={-1} className="t-h3 focus-target">
        {copy.title}
      </h2>
      <h3 className="t-h4">Ne oldu?</h3>
      <p>{copy.what}</p>
      <h3 className="t-h4">Şimdi ne yapabilirsiniz?</h3>
      <ul className="todo-list">
        {copy.todo.map((t) => (
          <li key={t}>{t}</li>
        ))}
      </ul>
      {error.requestId && (
        <p className="t-meta muted">
          Destek kodu: <code>{error.requestId}</code> · Sorunu bildirirken bu kodu paylaşabilirsiniz.
        </p>
      )}
      <div className="actions">
        {copy.retry && (
          <button type="button" className="btn" onClick={onRetry} disabled={left > 0}>
            {left > 0 ? `Yeniden dene (${left} sn)` : "Yeniden dene"}
          </button>
        )}
        <button type="button" className={copy.retry ? "btn btn-quiet" : "btn"} onClick={onEdit}>
          İçeriği düzenle
        </button>
      </div>
    </div>
  );
}
