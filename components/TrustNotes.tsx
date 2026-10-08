import { Section } from "./Section";
import { Icon, type IconName } from "./Icon";

const NOTE_ICONS: IconName[] = ["not-equal", "question", "external", "check"];

const NOTES = [
  { t: "Güven puanı kesinlik değildir.", d: "Bir puan gösterildiğinde bu, modelin kendi tahminidir; sonucun doğru olma olasılığı değildir. Puan yoksa uydurmayız. Asıl dayanak, altındaki kaynaklardır." },
  { t: "Kanıt yoksa “doğru” ya da “yanlış” demiyoruz.", d: "Yeterli kaynak bulunamazsa bunu açıkça “yeterli kanıt yok” olarak belirtiyoruz." },
  { t: "Bulunan kaynaklar görünür.", d: "Açıklamadaki atıflar listelenen kaynaklara bağlanır. Kaynak bulunamadığında bu da ayrıca belirtilir." },
  { t: "Sistem hata yapabilir.", d: "Sonuç otomatik bir ön değerlendirmedir. Önemli kararlar için kaynakları kendiniz de okuyun." },
];

export function TrustNotes() {
  return (
    <Section id="guven" title="Güven ilkeleri">
      <ul className="trust-list">
        {NOTES.map((n, i) => (
          <li key={n.t}>
            <span className="trust-icon"><Icon name={NOTE_ICONS[i]} /></span>
            <div>
            <strong>{n.t}</strong>
            <p>{n.d}</p>
            </div>
          </li>
        ))}
      </ul>
    </Section>
  );
}
