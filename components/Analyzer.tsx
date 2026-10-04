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
 * Kart yalnızca girişi, beklemeyi ve hatayı taşır; sonuç kartın dışında, kendi bölümünde açılır.
 * Yazılan içerik hata, vazgeçme ve düzenlemede kaybolmaz; yalnızca kullanıcı açıkça
 * "Yeni bir içerik incele" derse alan boşaltılır.
 */
export function Analyzer() {
  const { state, start, retry, reset, showSample } = useAnalysis();
  const formWrap = useRef<HTMLDivElement>(null);
  const sampleButton = useRef<HTMLButtonElement>(null);
  const prevPhase = useRef(state.phase);
  // "Yeni bir içerik incele" formu boşaltır (anahtar değişince alan sıfırdan kurulur).
  // "İçeriği düzenle" ve "Vazgeç" ise yazılanı korur.
  const [formKey, setFormKey] = useState(0);
  const startOver = () => {
    setFormKey((k) => k + 1);
    reset();
  };

  // Hata, vazgeçme ya da sonucu kapatmadan sonra odak forma döner. Form kullanılamıyorsa
  // (servis bağlı değil) odak, örneği açan düğmeye döner.
  useEffect(() => {
    if (prevPhase.current !== state.phase && state.phase === "idle") {
      const field = formWrap.current?.querySelector<HTMLElement>("textarea:not(:disabled), input[type=url]:not(:disabled)");
      (field ?? sampleButton.current)?.focus();
    }
    prevPhase.current = state.phase;
  }, [state.phase]);

  const busy = isBusy(state);

  // İnceleme sürerken sekme kapatılır ya da yenilenirse istek boşa gider (sonuç saklanmıyor);
  // tarayıcının kendi "ayrılmak istiyor musunuz?" sorusu yalnızca bu sırada açılır.
  useEffect(() => {
    if (!busy) return;
    const warn = (e: BeforeUnloadEvent) => e.preventDefault();
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [busy]);

  const completed = state.phase === "completed";
  /** Sabit örnek sonuç gösteriliyor (kullanıcı bir şey göndermedi). */
  const showcase = state.phase === "completed" && state.sample === true;

  return (
    <>
      <section className="analyzer" id="analyzer" aria-labelledby="analyzer-title" data-phase={state.phase}>
        {/* Sayfa başlığı zaten "inceleyin" diyor; kart başlığı görünür olsa aynı çağrı yinelenirdi. */}
        <h2 className="sr-only" id="analyzer-title">
          İçeriği inceleyin
        </h2>
        {apiInfo.usingMock && (
          <p className="note note--warn" role="note">
            <strong className="note-label">Geliştirme</strong>
            <span>Örnek kaynaklar uydurmadır; gerçek inceleme yapılmıyor.</span>
          </p>
        )}
        {apiInfo.unavailable && (
          <p className="note note--info" role="note" id={SERVICE_NOTE_ID}>
            <strong className="note-label">Bilgi</strong>
            <span>İnceleme servisi henüz bağlı değil; şu an içerik incelenemiyor.</span>
          </p>
        )}

        {/* JavaScript kapalıysa form çalışmaz; sessizce hiçbir şey yapmayan bir düğme yerine nedenini söyleriz. */}
        <noscript>
          <p className="note note--warn" role="note">
            <strong className="note-label">Uyarı</strong>
            <span>Bu sayfa JavaScript ile çalışır. İnceleme başlatmak için tarayıcınızda JavaScript&apos;i açın.</span>
          </p>
        </noscript>

        <div ref={formWrap} className="analyzer-input">
          <VerificationInput
            key={formKey}
            disabled={busy || apiInfo.unavailable}
            busy={busy}
            readOnly={completed && !showcase}
            onEdit={reset}
            onSubmit={start}
            noticeId={apiInfo.unavailable ? SERVICE_NOTE_ID : undefined}
            urlSupported={apiInfo.urlSupported}
            demoteSubmit={state.phase === "error"}
            examples={apiInfo.examples}
          />
        </div>

        {apiInfo.unavailable && !showcase && (
          <div className="examples">
            <p className="t-meta muted">Servis bağlanana kadar arayüzün ne ürettiğini örnek bir sonuçla görebilirsiniz.</p>
            <button ref={sampleButton} type="button" className="link-btn" onClick={showSample}>
              Örnek bir incelemeyi görüntüle
            </button>
          </div>
        )}

        {busy && <AnalysisProgress phase={state.phase} onCancel={reset} />}

        {state.phase === "error" && <ErrorState error={state.error} onRetry={retry} onEdit={reset} />}
      </section>

      {state.phase === "completed" && (
        <ResultView
          result={state.result}
          onReset={showcase ? reset : startOver}
          sample={apiInfo.usingMock || showcase}
          showcase={showcase}
        />
      )}
    </>
  );
}
