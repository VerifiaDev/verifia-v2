const STEPS = [
  { t: "İddialar ayrılır", d: "Gönderdiğiniz metindeki kaynaklarla kontrol edilebilir iddialar tek tek bulunur. Görüşler ve tahminler ayrı tutulur." },
  { t: "Kaynaklar aranır", d: "Her iddia için web’de ilgili kaynaklar toplanır." },
  { t: "Kanıtlar karşılaştırılır", d: "Kaynaklar iddiayla karşılaştırılır; destekleyen ve çelişen kanıtlar ayrı değerlendirilir." },
  { t: "Sonuç kanıtlarla verilir", d: "Sonucun yanında kaynağın adı, tarihi, alıntısı ve bağlantısı gösterilir. Kontrol etmek size kalır." },
];

export function HowItWorks() {
  return (
    <section id="nasil" className="section" aria-labelledby="nasil-title">
      <div className="container">
        <div className="section-head">
          <h2 id="nasil-title" className="t-h2">
            Nasıl çalışır?
          </h2>
        </div>
        <ol className="how-list">
          {STEPS.map((s, i) => (
            <li key={s.t}>
              <span className="how-num">Adım {i + 1}</span>
              <h3 className="t-h4">{s.t}</h3>
              <p>{s.d}</p>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}
