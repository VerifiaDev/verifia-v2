import { Section } from "./Section";
import { ProcessDemo } from "./ProcessDemo";

/**
 * Backend'in gerçek akışı (MertBulut11/verify, backend/main.py ve ai_engine.py). Burada yazan her şey koddan
 * doğrulanabilir; yapılmayan bir şey (ör. "destekleyen ve çelişen kanıtlar ayrı tartılır") yazılmaz.
 */
const STEPS = [
  {
    t: "İddialar ayrılır",
    d: "Metniniz bir yapay zekâ modeline gönderilir. Model, kaynaklarla kontrol edilebilecek iddiaları tek tek ayırır. Görüşler ve tahminler ayrıca listelenir, incelenmez.",
  },
  {
    t: "Kaynaklar aranır",
    d: "Her iddia için web’de arama yapılır ve en ilgili en fazla beş kaynak seçilir. Arama sonuçları her zaman en güvenilir kaynakları içermeyebilir.",
  },
  {
    t: "Kaynaklara göre karar verilir",
    d: "Model, yalnızca bulunan kaynaklara dayanarak karar vermeye ve her bilgiye kaynağını numarayla eklemeye yönlendirilir. Hiç kaynak bulunamayan iddiaya “yeterli kanıt yok” denir.",
  },
  {
    t: "Sonuç ve kaynaklar birlikte gösterilir",
    d: "Kanıtlar destekliyor, çelişiyor, kaynaklar birbiriyle çelişiyor ya da yeterli kanıt yok. Sonuç otomatik bir ön değerlendirmedir; kaynakları kendiniz de okuyun.",
  },
];

export function HowItWorks() {
  return (
    <Section id="nasil" title="Nasıl çalışır?">
      <ProcessDemo />
      <ol className="how-list">
        {STEPS.map((s, i) => (
          <li key={s.t}>
            {/* Sıra bilgisi <ol> ile zaten duyurulur; rakam yalnızca görseldir. */}
            <span className="how-num" aria-hidden="true">
              {i + 1}
            </span>
            <div>
              <h3 className="t-h4">{s.t}</h3>
              <p>{s.d}</p>
            </div>
          </li>
        ))}
      </ol>
    </Section>
  );
}
