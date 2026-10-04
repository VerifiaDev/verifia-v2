"use client";

import { useEffect, useRef } from "react";
import type { BusyPhase } from "@/hooks/useAnalysis";

interface Props {
  onCancel: () => void;
  /**
   * Hangi aşamada olduğumuz. `submitting` ise (backend aşama bilgisi vermiyor) hiçbir adım
   * "şu an burada" diye işaretlenmez: sahte ilerleme gösterilmez.
   */
  phase: BusyPhase;
}

const ACTIVE_STEP: Record<BusyPhase, number | undefined> = {
  submitting: undefined,
  extracting_claims: 0,
  retrieving_evidence: 1,
  verifying: 2,
};

const STEPS = ["İddialar çıkarılıyor", "Kaynaklar aranıyor", "Kanıtlar karşılaştırılıyor"];

/** Gerçek bir bekleme durumu. Yüzde ya da uydurma adım ilerlemesi göstermez. */
export function AnalysisProgress({ onCancel, phase }: Props) {
  const activeStep = ACTIVE_STEP[phase];
  const headingRef = useRef<HTMLHeadingElement>(null);

  // Gönder düğmesi devre dışı kalınca odak sayfa başına düşer; bekleme durumunu görünür alana
  // getirmek ve odağı korumak için odağı başlığa taşırız. (Aşama değişince yeniden çalışmaz.)
  useEffect(() => {
    headingRef.current?.focus();
  }, []);

  return (
    <div className="state analysis-progress" role="status" aria-live="polite">
      <h2 ref={headingRef} tabIndex={-1} className="t-h3 focus-target">
        İçerik inceleniyor
      </h2>
      <p>Bu işlem iddia sayısına göre zaman alabilir. Sayfayı kapatmadan bekleyin.</p>
      <ol className="progress-steps">
        {STEPS.map((s, i) => (
          <li key={s} aria-current={activeStep === i ? "step" : undefined} data-complete={activeStep !== undefined && i < activeStep}>
            {s}
            {activeStep !== undefined && i < activeStep && <span className="muted"> — tamamlandı</span>}
          </li>
        ))}
      </ol>
      {activeStep === undefined && (
        <p className="muted t-meta">Adımlar, sistemin sırayla yaptığı işleri gösterir; şu anki adım bilgisi alınmıyor.</p>
      )}
      <button type="button" className="btn btn-quiet" onClick={onCancel}>
        Vazgeç
      </button>
    </div>
  );
}
