/**
 * Metindeki alt çizgilerin ne anlama geldiği. "Nasıl çalışır?" canlandırmasının ve sonuç sayfasının altında durur.
 * Renk tek başına anlam taşımaz: her çizginin yanında adı yazılıdır.
 */
export function UnderlineKey() {
  return (
    <section className="ul-key" aria-labelledby="ul-key-title">
      <h3 id="ul-key-title" className="t-h4">Alt çizgiler ne anlama geliyor?</h3>
      <ul>
        <li><span className="ul-sample ul-ok">Yeşil</span><span>Kanıtlar iddiayı destekliyor. İddianın tamamı doğru.</span></li>
        <li><span className="ul-sample ul-bad">Kırmızı</span><span>Kanıtlar iddiayla çelişiyor ya da kaynaklar birbiriyle çelişiyor. Bir cümlenin yalnızca bir kısmı yanlışsa sadece o kısım kırmızıdır.</span></li>
        <li><span className="ul-sample ul-unknown">Mavi</span><span>Yeterli kanıt yok. İddia ne doğrulanabildi ne yanlışlanabildi.</span></li>
        <li><span className="ul-sample ul-opinion">Noktalı gri</span><span>Görüş ya da tahmin. Kaynaklarla incelenmez.</span></li>
      </ul>
    </section>
  );
}
