"use client";

import { useEffect, useRef } from "react";
import { isBusy, useAnalysis } from "@/hooks/useAnalysis";
import { AnalysisProgress } from "./AnalysisProgress";
import { ErrorState } from "./ErrorState";
import { ResultView } from "./ResultView";
import { VerificationInput } from "./VerificationInput";
import { apiInfo } from "@/lib/api";

/**
 * Sayfanın etkileşimli kısmı. Durumlar: bkz. hooks/useAnalysis.ts.
 * Form yalnızca sonuç görünürken gizlenir; ama her zaman bağlı kalır (yazılan içerik kaybolmaz).
 */
export function Analyzer() {
  const { state, start, retry, reset } = useAnalysis();
  const formWrap = useRef<HTMLDivElement>(null);
  const prevPhase = useRef(state.phase);

  // Hata ya da vazgeçmeden sonra odak forma döner.
  useEffect(() => {
    if (prevPhase.current !== state.phase && state.phase === "idle") {
      formWrap.current?.querySelector<HTMLElement>("textarea, input[type=url]")?.focus();
    }
    prevPhase.current = state.phase;
  }, [state.phase]);

  const showForm = state.phase !== "completed";

  return (
    <div>
      {apiInfo.usingMock && (
        <p className="mock-note" role="note">
          Şu an örnek verilerle çalışıyor. Gösterilen kaynaklar uydurmadır; gerçek bir doğrulama değildir.
        </p>
      )}

      <div ref={formWrap} hidden={!showForm}>
        <VerificationInput
          disabled={isBusy(state)}
          onSubmit={start}
          examples={apiInfo.examples}
        />
      </div>

      {state.phase === "idle" && (
        <div className="state">
          <h2 className="t-h4">Henüz bir içerik göndermediniz</h2>
          <p className="muted">
            Bir metin ya da bağlantı gönderin. Sonuç burada, iddia iddia ve kaynaklarıyla birlikte görünecek.
          </p>
        </div>
      )}

      {isBusy(state) && <AnalysisProgress phase={state.phase} onCancel={reset} />}

      {state.phase === "error" && <ErrorState error={state.error} onRetry={retry} onEdit={reset} />}

      {state.phase === "completed" && <ResultView result={state.result} input={state.input} onReset={reset} />}
    </div>
  );
}
