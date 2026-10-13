"use client";

import { useEffect, useRef, useState } from "react";
import { isBusy, sampleEntryVisible, useAnalysis } from "@/hooks/useAnalysis";
import { AnalysisProgress } from "./AnalysisProgress";
import { ErrorState } from "./ErrorState";
import { ResultView } from "./ResultView";
import { VerificationInput } from "./VerificationInput";
import { apiInfo } from "@/lib/api";
import { Icon } from "./Icon";
import { LegendDisclosure } from "./Legend";
import type { CheckRequest } from "@/lib/types";

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
  const exampleQuery = useRef(false);
  const prevPhase = useRef(state.phase);
  // "Yeni bir içerik incele" formu boşaltır (anahtar değişince alan sıfırdan kurulur).
  // "İçeriği düzenle" ve "Vazgeç" ise yazılanı korur.
  const [formKey, setFormKey] = useState(0);
  const [submitted, setSubmitted] = useState<CheckRequest | null>(null);
  useEffect(() => {
    const syncExample = () => {
      const next = new URLSearchParams(window.location.search).get("example") === "apollo-11";
      if (next === exampleQuery.current) return;
      exampleQuery.current = next;
      if (next) showSample(); else reset();
    };
    syncExample();
    window.addEventListener("popstate", syncExample);
    return () => window.removeEventListener("popstate", syncExample);
  }, [showSample, reset]);
  function openSample() {
    exampleQuery.current = true;
    const url = new URL(window.location.href);
    url.searchParams.set("example", "apollo-11");
    url.hash = "report";
    // Yeni geçmiş kaydı: tarayıcının "Geri" tuşu örneği kapatıp forma döner (siteden çıkmaz).
    // Geri gelindiğinde adreste `example` kalmaz; yukarıdaki popstate dinleyicisi örneği kapatır.
    window.history.pushState(null, "", url);
    showSample();
  }
  function clearExampleUrl() {
    exampleQuery.current = false;
    const url = new URL(window.location.href);
    url.searchParams.delete("example");
    url.hash = "analyzer";
    window.history.replaceState(null, "", url);
  }
  function closeSample() {
    clearExampleUrl();
    reset();
  }
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
            <span>Geliştirici senaryoları temsili veri kullanır; gerçek inceleme yapılmıyor. Apollo 11 raporu ayrıca kaynaklandırılmış hazır örnektir.</span>
          </p>
        )}
        {apiInfo.unavailable && <p className="service-status t-meta" id={SERVICE_NOTE_ID}>
          <strong>Demo sürümü.</strong> Canlı inceleme henüz bağlı değil. Yazdığınız metin gönderilmez.
        </p>}

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
            disabled={busy}
            unavailable={apiInfo.unavailable}
            localOnly={apiInfo.usingMock}
            busy={busy}
            readOnly={completed && !showcase}
            onEdit={reset}
            onSubmit={(request) => { if (exampleQuery.current) clearExampleUrl(); setSubmitted(request); void start(request); }}
            noticeId={apiInfo.unavailable ? SERVICE_NOTE_ID : undefined}
            urlSupported={apiInfo.urlSupported}
            demoteSubmit={state.phase === "error"}
            examples={apiInfo.examples}
          />
        </div>

        {/* Hazır örnek rapor her modda sunulur (canlıda da): backend'e istek göndermez, kota harcamaz ve
            açıldığında "Önceden hazırlanmış örnek rapor. Canlı analiz değildir." etiketini taşır.
            Sonuç ekrandayken sunulmaz (bkz. sampleEntryVisible). */}
        {sampleEntryVisible(state) && <div className="sample-entry">
          <button ref={sampleButton} type="button" className={apiInfo.unavailable ? "btn" : "btn btn-quiet"} onClick={openSample} disabled={busy}>
            Kaynaklı örnek raporu aç <Icon name="chevron" />
          </button>
          <p className="t-meta muted">Apollo 11 · Gerçek NASA bağlantıları · Hazır örnek; yazdığınız metni incelemez.</p>
        </div>}

        {busy && <AnalysisProgress phase={state.phase} onCancel={reset} />}

        {state.phase === "error" && <ErrorState error={state.error} onRetry={retry} onEdit={reset} />}
      </section>

      {!completed && <LegendDisclosure />}
      {state.phase === "completed" && (
        <ResultView
          result={state.result}
          onReset={showcase ? closeSample : startOver}
          sample={apiInfo.usingMock || showcase}
          showcase={showcase}
          input={showcase ? undefined : submitted?.content}
        />
      )}
    </>
  );
}
