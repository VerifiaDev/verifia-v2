"use client";

import { useEffect, useRef, useState } from "react";
import { isBusy, useAnalysis } from "@/hooks/useAnalysis";
import { AnalysisProgress } from "./AnalysisProgress";
import { ErrorState } from "./ErrorState";
import { ResultView } from "./ResultView";
import { VerificationInput } from "./VerificationInput";
import { apiInfo } from "@/lib/api";

const SERVICE_NOTE_ID = "service-note";

/**
 * Sayfanın etkileşimli kısmı. Durumlar: bkz. hooks/useAnalysis.ts.
 * Form, bekleme ve sonuç aynı yüzeyde kalır; yazılan içerik hata, vazgeçme ve düzenlemede kaybolmaz.
 * Yalnızca kullanıcı açıkça "Yeni bir içerik incele" derse alan boşaltılır.
 */
export function Analyzer() {
  const { state, start, retry, reset } = useAnalysis();
  const formWrap = useRef<HTMLDivElement>(null);
  const prevPhase = useRef(state.phase);
  // "Yeni bir içerik incele" formu boşaltır (anahtar değişince alan sıfırdan kurulur).
  // "İçeriği düzenle" ve "Vazgeç" ise yazılanı korur.
  const [formKey, setFormKey] = useState(0);
  const startOver = () => {
    setFormKey((k) => k + 1);
    reset();
  };

  // Hata ya da vazgeçmeden sonra odak forma döner.
  useEffect(() => {
    if (prevPhase.current !== state.phase && state.phase === "idle") {
      formWrap.current?.querySelector<HTMLElement>("textarea, input[type=url]")?.focus();
    }
    prevPhase.current = state.phase;
  }, [state.phase]);

  const busy = isBusy(state);
  const completed = state.phase === "completed";

  return (
    <section className="analyzer" id="analyzer" aria-labelledby="analyzer-title" data-phase={state.phase}>
      <h2 className="t-h2 analyzer-title" id="analyzer-title">İçeriği inceleyin</h2>
      {apiInfo.usingMock && (
        <p className="mock-note" role="note">
          <strong className="mock-label">Geliştirme</strong>
          <span>Örnek kaynaklar uydurmadır; gerçek inceleme yapılmıyor.</span>
        </p>
      )}
      {apiInfo.unavailable && (
        <p className="mock-note" role="note" id={SERVICE_NOTE_ID}>
          <strong className="mock-label">Bilgi</strong>
          <span>İnceleme servisi henüz bağlı değil; şu an içerik incelenemiyor.</span>
        </p>
      )}

      <div ref={formWrap} className="analyzer-input">
        <VerificationInput
          key={formKey}
          disabled={busy || apiInfo.unavailable}
          busy={busy}
          readOnly={completed}
          onEdit={reset}
          onSubmit={start}
          noticeId={apiInfo.unavailable ? SERVICE_NOTE_ID : undefined}
          examples={apiInfo.examples}
        />
      </div>

      {busy && <AnalysisProgress phase={state.phase} onCancel={reset} />}

      {state.phase === "error" && <ErrorState error={state.error} onRetry={retry} onEdit={reset} />}

      {state.phase === "completed" && (
        <ResultView result={state.result} onReset={startOver} sample={apiInfo.usingMock} />
      )}
    </section>
  );
}
