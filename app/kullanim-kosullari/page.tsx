import type { Metadata } from "next";
import { EmailLink, LegalPage, Owner } from "@/components/LegalPage";
import { LEGAL_COMPLETE, PRIVACY_PATH, TERMS_PATH } from "@/lib/legal";
import { SITE_NAME } from "@/lib/config";
import { SITE_ORIGIN } from "@/lib/site";

export const metadata: Metadata = {
  title: `Kullanım koşulları | ${SITE_NAME}`,
  description: "verify'ın ne olduğu, sınırları, ücret ve iade durumu ve kullanırken uyulması gereken kurallar.",
  ...(SITE_ORIGIN ? { alternates: { canonical: TERMS_PATH } } : {}),
  ...(LEGAL_COMPLETE ? {} : { robots: { index: false, follow: false } }),
};

/** Hizmetin gerçek davranışına dayanır; hukuki metin değildir, yayından önce hukukçu kontrolü önerilir. */
export default function TermsPage() {
  return (
    <LegalPage title="Kullanım koşulları" path={TERMS_PATH}>
      <p>verify&apos;ı kullanarak aşağıdaki koşulları kabul etmiş olursunuz.</p>

      <h2>Hizmeti sunan</h2>
      <p>
        Bu site, <Owner /> ticari olmayan bir projesidir. İletişim: <EmailLink />
      </p>

      <h2>Hizmet nedir?</h2>
      <p>
        verify, yapıştırdığınız metindeki iddiaları ayırır, her iddia için web&apos;de kaynak arar ve bulunan kaynaklara
        göre otomatik bir ön değerlendirme gösterir. Değerlendirmeyi bir yapay zekâ modeli yapar; bir insan editör
        sonucu kontrol etmez.
      </p>

      <h2>Sonuçlar kesin hüküm değildir</h2>
      <ul>
        <li>Sonuçlar hatalı ya da eksik olabilir. Bir iddianın doğru ya da yanlış olduğunu kesin olarak söylemez.</li>
        <li>Önemli bir karar vermeden önce gösterilen kaynakları kendiniz okuyun.</li>
        <li>
          &quot;Yeterli kanıt yok&quot; sonucu, iddianın yanlış olduğu anlamına gelmez; yalnızca bulunan kaynakların
          yetmediğini gösterir.
        </li>
        <li>Sonuçlar bir kişi ya da kurum hakkında verilmiş bir hüküm değildir.</li>
      </ul>

      <h2>Sonuçları paylaşırken</h2>
      <ul>
        <li>Sonucun otomatik bir ön değerlendirme olduğunu belirtin; verify tarafından verilmiş kesin bir doğrulama gibi sunmayın.</li>
        <li>Sonuçları bir kişiyi ya da kurumu küçük düşürmek veya okuyanları yanıltmak için kullanmayın.</li>
        <li>Paylaştığınız içerikten siz sorumlusunuz.</li>
      </ul>

      <h2>Kaynaklar</h2>
      <p>
        Gösterilen kaynaklar üçüncü taraf sitelerdir. İçeriklerini biz hazırlamayız ve doğruluklarını garanti etmeyiz.
        Kaynaklardan yapılan kısa alıntılar, yalnızca değerlendirmenin dayanağını göstermek için ve kaynağı belirtilerek
        gösterilir; bu içeriklerin hakları sahiplerine aittir. Tam metni kaynağın kendi sayfasında okuyun.
      </p>

      <h2>Kullanım kuralları</h2>
      <ul>
        <li>
          Kişisel ya da özel nitelikli veri içeren metin göndermeyin (ayrıntılar{" "}
          <a href={PRIVACY_PATH}>gizlilik politikasında</a>).
        </li>
        <li>Hukuka aykırı içerik ya da başkalarının haklarını ihlal eden içerik göndermeyin.</li>
        <li>Hizmete otomatik araçlarla toplu istek göndermeyin ya da hizmetin çalışmasını bozmaya çalışmayın.</li>
      </ul>

      <h2>Ücret ve iade</h2>
      <p>
        verify ücretsizdir. Ödeme alınmaz; ürün, abonelik ya da ücretli bir özellik satılmaz. Bu nedenle iade edilecek
        bir ödeme ve iade politikası yoktur. İleride ücretli bir özellik eklenirse fiyatı ve iade koşulları, ödeme
        alınmadan önce bu sayfada yayımlanır.
      </p>

      <h2>Sorumluluk</h2>
      <p>
        Hizmet olduğu gibi sunulur. Kanunun izin verdiği ölçüde, sonuçlara dayanılarak verilen kararlardan ya da hizmetin
        kesintiye uğramasından doğan zararlardan sorumluluk kabul edilmez.
      </p>

      <h2>Hizmetin sürekliliği</h2>
      <p>
        Hizmet zaman zaman yavaşlayabilir ya da kullanılamayabilir. Kötüye kullanımı önlemek için istek sayısı
        sınırlanabilir. Özellikler önceden haber verilmeden değişebilir ya da kaldırılabilir.
      </p>

      <h2>Uygulanacak hukuk</h2>
      <p>Bu koşullara Türkiye Cumhuriyeti hukuku uygulanır.</p>

      <h2>Değişiklikler ve iletişim</h2>
      <p>
        Bu koşullar değişirse güncel hâli bu sayfada, yeni tarihiyle yayımlanır. Sorularınız için: <EmailLink />
      </p>
    </LegalPage>
  );
}
