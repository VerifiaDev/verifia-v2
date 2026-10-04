import { Section } from "./Section";

const STEPS = [
  { t: "İddialar ayrılır", d: "Gönderdiğiniz metindeki kaynaklarla kontrol edilebilir iddialar tek tek bulunur. Görüşler ve tahminler ayrı tutulur." },
  { t: "Kaynaklar aranır", d: "Her iddia için web’de ilgili kaynaklar toplanır." },
  { t: "Kanıtlar karşılaştırılır", d: "Kaynaklar iddiayla karşılaştırılır; destekleyen ve çelişen kanıtlar ayrı değerlendirilir." },
  { t: "Kanıt düzeyi açıkça belirtilir", d: "Kaynaklar iddiayı destekliyor, onunla çelişiyor ya da yeterli gelmiyorsa sonuç bunu gösterir." },
];

export function HowItWorks() {
  return (
    <Section id="nasil" title="Nasıl çalışır?">
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
