interface Props {
  onCancel: () => void;
  /**
   * Backend aşama bilgisi verirse (0-3) o adım vurgulanır.
   * Verilmezse hiçbir adım "şu an burada" diye işaretlenmez: sahte ilerleme gösterilmez.
   */
  activeStep?: number;
}

const STEPS = ["İddialar çıkarılıyor", "Kaynaklar aranıyor", "Kanıtlar karşılaştırılıyor"];

/** Gerçek bir bekleme durumu. Yüzde ya da uydurma adım ilerlemesi göstermez. */
export function AnalysisProgress({ onCancel, activeStep }: Props) {
  return (
    <div className="state" role="status" aria-live="polite">
      <h2 className="t-h3">İçerik inceleniyor</h2>
      <p>Bu işlem, iddia sayısına göre bir dakikaya kadar sürebilir. Sayfayı kapatmadan bekleyin.</p>
      <ol className="progress-steps">
        {STEPS.map((s, i) => (
          <li key={s} aria-current={activeStep === i ? "step" : undefined}>
            {s}
          </li>
        ))}
      </ol>
      <p className="muted t-meta">Adımlar, sistemin sırayla yaptığı işleri gösterir; şu anki adım bilgisi alınmıyor.</p>
      <button type="button" className="btn btn-quiet" onClick={onCancel}>
        Vazgeç
      </button>
    </div>
  );
}
