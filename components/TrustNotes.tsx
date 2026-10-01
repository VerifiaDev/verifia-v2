import { Section } from "./Section";

const NOTES = [
  { t: "Güven yüzdesi göstermiyoruz.", d: "Yapay zekâ modellerinin verdiği yüzdeler ölçülmüş bir doğruluk değildir; bu yüzden sonuçta sayı yerine kanıt görürsünüz." },
  { t: "Kanıt yoksa “doğru” ya da “yanlış” demiyoruz.", d: "Yeterli kaynak bulunamazsa bunu açıkça “yeterli kanıt yok” olarak belirtiyoruz." },
  { t: "Her sonucun kaynağı görünür.", d: "Açıklamadaki her atıf, aşağıdaki kaynak listesindeki bir kayda bağlanır. Listede olmayan kaynak gösterilmez." },
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
