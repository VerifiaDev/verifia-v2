import type { Metadata } from "next";
import { EmailLink, LegalPage } from "@/components/LegalPage";
import { LEGAL_COMPLETE, PRIVACY_PATH, TERMS_PATH } from "@/lib/legal";
import { SITE_NAME } from "@/lib/config";
import { SITE_ORIGIN } from "@/lib/site";

export const metadata: Metadata = {
  title: `Kullanım koşulları | ${SITE_NAME}`,
  description: "verify'ın ne olduğu, sınırları ve kullanırken uyulması gereken kurallar.",
  ...(SITE_ORIGIN ? { alternates: { canonical: TERMS_PATH } } : {}),
  ...(LEGAL_COMPLETE ? {} : { robots: { index: false, follow: false } }),
};

/** Hizmetin gerçek davranışına dayanır; hukuki metin değildir, yayından önce hukukçu kontrolü önerilir. */
export default function TermsPage() {
  return (
    <LegalPage title="Kullanım koşulları" other="privacy">
      <p>verify&apos;ı kullanarak aşağıdaki koşulları kabul etmiş olursunuz.</p>

      <h2>Hizmet nedir?</h2>
      <p>
        verify, yapıştırdığınız metindeki iddiaları ayırır, her iddia için web&apos;de kaynak arar ve bulunan kaynaklara
        göre otomatik bir ön değerlendirme gösterir. Değerlendirmeyi bir yapay zekâ modeli yapar.
      </p>

      <h2>Sonuçlar kesin hüküm değildir</h2>
      <ul>
        <li>Sonuçlar hatalı ya da eksik olabilir. Bir iddianın doğru ya da yanlış olduğunu kesin olarak söylemez.</li>
        <li>Önemli bir karar vermeden önce gösterilen kaynakları kendiniz okuyun.</li>
        <li>
          &quot;Yeterli kanıt yok&quot; sonucu, iddianın yanlış olduğu anlamına gelmez; yalnızca bulunan kaynakların
          yetmediğini gösterir.
        </li>
        <li>Sonuçları, verify tarafından verilmiş kesin bir doğrulama gibi sunmayın.</li>
      </ul>

      <h2>Kaynaklar</h2>
      <p>
        Gösterilen kaynaklar üçüncü taraf sitelerdir. İçeriklerini biz hazırlamayız ve doğruluklarını garanti etmeyiz.
      </p>

      <h2>Kullanım kuralları</h2>
      <ul>
        <li>
          Kişisel ya da özel nitelikli veri içeren metin göndermeyin (ayrıntılar{" "}
          <a href={PRIVACY_PATH}>gizlilik politikasında</a>).
        </li>
        <li>Hukuka aykırı içerik göndermeyin.</li>
        <li>Hizmete otomatik araçlarla toplu istek göndermeyin ya da hizmetin çalışmasını bozmaya çalışmayın.</li>
      </ul>

      <h2>Hizmetin sürekliliği</h2>
      <p>
        Hizmet zaman zaman yavaşlayabilir ya da kullanılamayabilir. Özellikler önceden haber verilmeden değişebilir ya da
        kaldırılabilir.
      </p>

      <h2>Değişiklikler ve iletişim</h2>
      <p>
        Bu koşullar değişirse güncel hâli bu sayfada, yeni tarihiyle yayımlanır. Sorularınız için: <EmailLink />
      </p>
    </LegalPage>
  );
}
