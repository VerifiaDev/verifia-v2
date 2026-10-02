import { Section } from "./Section";

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
        {NOTES.map((n) => (
          <li key={n.t}>
            <strong>{n.t}</strong>
            <p>{n.d}</p>
          </li>
        ))}
      </ul>
    </Section>
  );
}
