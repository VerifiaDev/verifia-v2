"use client";

import { useEffect, useRef, useState } from "react";
import type { BusyPhase } from "@/hooks/useAnalysis";
import { HEALTH_TIMEOUT_MS, REQUEST_TIMEOUT_MS } from "@/lib/config";

interface Props {
  onCancel: () => void;
  /**
   * Hangi aşamada olduğumuz. `submitting` ise backend aşama bilgisi vermiyordur: adım listesi hiç
   * gösterilmez (ilerlemeyen bir liste "takıldı" izlenimi verir); yalnızca geçen süre gösterilir.
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

/** Bu kadar saniyeden sonra "hâlâ sürüyor, vazgeçebilirsiniz" notu eklenir. */
const LONG_WAIT_SECONDS = 30;

/**
 * Arayüzün en fazla bekleyeceği süre (sunucu denetimi + inceleme). Bir vaat değil, üst sınırdır:
 * bu süre dolarsa kullanıcıya zaman aşımı söylenir. 150 sn → "2,5 dakika".
 */
export function maxWaitLabel(ms: number = HEALTH_TIMEOUT_MS + REQUEST_TIMEOUT_MS): string {
  const minutes = Math.round((ms / 60_000) * 2) / 2;
  return `${String(minutes).replace(".", ",")} dakika`;
}

/** 75 → "1:15". Sözcük kullanılmaz: süre vaat etmez, yalnızca sayar. */
function clock(seconds: number): string {
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
}

/**
 * Gerçek bir bekleme durumu. Yüzde ya da uydurma adım ilerlemesi göstermez; geçen süre gerçek bilgidir.
 * Başlangıç odakla duyurulur (odak başlığa taşınır). Backend aşama bildirirse yalnızca o aşamanın adı
 * kısa bir durum satırıyla okunur; panelin tamamı her değişimde yeniden okunmaz. Süre sayacı canlı bölge
 * değildir (her saniye okunmasın).
 */
export function AnalysisProgress({ onCancel, phase }: Props) {
  const activeStep = ACTIVE_STEP[phase];
  const headingRef = useRef<HTMLHeadingElement>(null);
  const [elapsed, setElapsed] = useState(0);

  // Gönder düğmesi devre dışı kalınca odak sayfa başına düşer; bekleme durumunu görünür alana
  // getirmek ve odağı korumak için odağı başlığa taşırız. (Aşama değişince yeniden çalışmaz.)
  useEffect(() => {
    headingRef.current?.focus();
  }, []);

  useEffect(() => {
    const startedAt = Date.now();
    const id = setInterval(() => setElapsed(Math.floor((Date.now() - startedAt) / 1000)), 1000);
    return () => clearInterval(id);
  }, []);

  return (
    <div className="state analysis-progress">
      <h2 ref={headingRef} tabIndex={-1} className="t-h3 focus-target">
        İçerik inceleniyor
      </h2>
      <p>
        Bu işlem iddia sayısına göre zaman alabilir. Sunucu bir süredir kullanılmadıysa önce açılması gerekir. Yanıt
        gelmezse en geç {maxWaitLabel()} sonra bunu bildiririz; sayfayı kapatmadan bekleyin.
      </p>
      {activeStep !== undefined && (
        <ol className="progress-steps">
          {STEPS.map((s, i) => (
            <li key={s} aria-current={activeStep === i ? "step" : undefined} data-complete={i < activeStep}>
              {s}
              {i < activeStep && <span className="muted"> — tamamlandı</span>}
            </li>
          ))}
        </ol>
      )}
      <p className="sr-only" role="status">
        {activeStep !== undefined ? `${STEPS[activeStep]} (adım ${activeStep + 1} / ${STEPS.length})` : ""}
      </p>
      <p className="progress-elapsed muted t-meta">
        Geçen süre: <span className="tnum">{clock(elapsed)}</span>
      </p>
      {elapsed >= LONG_WAIT_SECONDS && (
        <p className="t-meta">
          İnceleme sürüyor. Beklemeye devam edebilir ya da vazgeçip daha kısa bir metinle yeniden deneyebilirsiniz.
        </p>
      )}
      <button type="button" className="btn btn-quiet" onClick={onCancel}>
        Vazgeç
      </button>
    </div>
  );
}
