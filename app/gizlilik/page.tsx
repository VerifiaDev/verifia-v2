import type { Metadata } from "next";
import { EmailLink, ExternalLink, LegalPage, Owner } from "@/components/LegalPage";
import { COOKIES_PATH, LEGAL_COMPLETE, PRIVACY_PATH, PROVIDERS, TERMS_PATH } from "@/lib/legal";
import { SITE_NAME } from "@/lib/config";
import { SITE_ORIGIN } from "@/lib/site";

export const metadata: Metadata = {
  title: `Gizlilik politikası | ${SITE_NAME}`,
  description: "verify'a gönderdiğiniz metnin nasıl işlendiği, kimlere iletildiği, ne kadar saklandığı ve haklarınız.",
  ...(SITE_ORIGIN ? { alternates: { canonical: PRIVACY_PATH } } : {}),
  ...(LEGAL_COMPLETE ? {} : { robots: { index: false, follow: false } }),
};

/**
 * KVKK m.10 aydınlatma yükümlülüğünün başlıkları: veri sorumlusu, amaç, aktarım, yöntem ve hukuki sebep, haklar.
 * Her cümle doğrulanabilir bir davranışa dayanır (16 Ekim 2026):
 * - site: lib/api (metin yalnızca "İncelemeyi başlat" ile gönderilir), components/ThemeToggle (tek tarayıcı kaydı);
 * - canlı backend v1 (MertBulut11/verify): metin Groq'a, iddialardan üretilen sorgular Tavily'ye gider; arama
 *   sorguları sunucu çıktısına yazılır (backend/search_retrieval.py, coklu_internet_aramasi);
 * - sağlayıcı belgeleri: Render log saklama 7/14/30 gün (render.com/docs/logging), Groq "your data",
 *   Tavily gizlilik politikası.
 * backend_v2 yayına alınırsa (6 saatlik bellek önbelleği vb.) bu sayfa güncellenmelidir.
 */
export default function PrivacyPage() {
  return (
    <LegalPage title="Gizlilik politikası" path={PRIVACY_PATH}>
      <p>
        Bu metin, verify&apos;ı kullanırken hangi bilgilerin işlendiğini anlatır ve 6698 sayılı Kişisel Verilerin
        Korunması Kanunu&apos;nun (KVKK) 10. maddesi kapsamındaki aydınlatma metnidir. verify hesap açtırmaz; adınızı,
        e-posta adresinizi ya da başka bir kimlik bilginizi istemez.
      </p>

      <h2>Veri sorumlusu</h2>
      <p>
        Bu site, <Owner /> ticari olmayan bir projesidir. İletişim: <EmailLink />
      </p>

      <h2>Hangi bilgiler işlenir?</h2>
      <ul>
        <li>
          <strong>İncelemek için gönderdiğiniz metin.</strong> Yalnızca &quot;İncelemeyi başlat&quot; düğmesine
          bastığınızda gönderilir. Metin alanına yazmak tek başına hiçbir şey göndermez.
        </li>
        <li>
          <strong>Bağlantıya ait teknik bilgiler:</strong> IP adresi, tarayıcı türü, istenen sayfa ve istek zamanı. Siteyi
          ve inceleme sunucusunu barındıran hizmetler bu bilgileri her web sitesinde olduğu gibi kaydeder.
        </li>
        <li>
          <strong>Tema tercihi:</strong> Gece modu düğmesine bastığınızda seçiminiz yalnızca kendi tarayıcınızda saklanır,
          bize gönderilmez. Ayrıntılar <a href={COOKIES_PATH}>çerez politikasında</a>.
        </li>
      </ul>
      <p>Çerez, reklam, ziyaretçi analizi (analitik) ya da başka sitelerden yüklenen içerik kullanılmaz.</p>

      <h2>Neden ve hangi hukuki sebeple işlenir?</h2>
      <ul>
        <li>
          Metniniz, sizin başlattığınız incelemeyi yapmak için işlenir: iddiaları ayırmak, her iddia için kaynak aramak ve
          sonucu size göstermek. Hukuki sebep, istediğiniz hizmetin sunulması için gerekli olmasıdır (KVKK m.5/2-c).
        </li>
        <li>
          Teknik bilgiler, sitenin çalışması, güvenliği ve kötüye kullanımın önlenmesi için işlenir. Hukuki sebep meşru
          menfaattir (KVKK m.5/2-f).
        </li>
      </ul>
      <p>Bilgiler sitedeki form aracılığıyla ve bağlantı sırasında otomatik olarak toplanır.</p>

      <h2>Bilgiler kimlere iletilir?</h2>
      <ul>
        <li>
          <strong>{PROVIDERS.vercel.name}</strong> siteyi barındırır. Siteyi açtığınızda bağlantıya ait teknik bilgileri
          işler. <ExternalLink href={PROVIDERS.vercel.policy}>Vercel gizlilik bildirimi</ExternalLink>
        </li>
        <li>
          <strong>{PROVIDERS.render.name}</strong> inceleme sunucumuzu barındırır. Metninizin tamamı önce buraya gelir.
          Sunucu kayıtlarında IP adresiniz ve metninizden üretilen web araması sorguları yer alabilir.{" "}
          <ExternalLink href={PROVIDERS.render.policy}>Render gizlilik politikası</ExternalLink>
        </li>
        <li>
          <strong>{PROVIDERS.groq.name}</strong>, iddiaları ayıran ve kaynaklara göre değerlendiren yapay zekâ modelini
          çalıştırır. Metninizin tamamı ve bulunan kaynakların alıntıları buraya gönderilir. Groq bu içerikleri varsayılan
          olarak saklamadığını, ancak arıza ve kötüye kullanım incelemesi için 30 güne kadar saklayabileceğini belirtir.{" "}
          <ExternalLink href={PROVIDERS.groq.policy}>Groq veri politikası</ExternalLink>
        </li>
        <li>
          <strong>{PROVIDERS.tavily.name}</strong> web araması yapar. Metninizden ayrılan iddialara dayanan arama
          sorguları buraya gönderilir. Tavily, sorguları hizmetini geliştirmek için saklayabileceğini ve sınırlı
          durumlarda başka arama sağlayıcılarıyla (ör. Google) paylaşabileceğini belirtir.{" "}
          <ExternalLink href={PROVIDERS.tavily.policy}>Tavily gizlilik politikası</ExternalLink>
        </li>
      </ul>
      <p>
        Bu hizmet sağlayıcılarının tamamı yurt dışındadır: Groq verileri Amerika Birleşik Devletleri&apos;nde saklar,
        Tavily ABD merkezli bir şirkettir. Bu nedenle gönderdiğiniz metin yurt dışına aktarılır. Arama sonucunda bulunan
        sayfalar sunucumuz tarafından açılır; o sitelere metniniz ya da IP adresiniz gönderilmez. Bu bilgileri satmayız
        ve reklam için kullanmayız.
      </p>

      <h2>Ne kadar saklanır?</h2>
      <ul>
        <li>
          Metniniz ve sonuçlarınız tarafımızdan bir veritabanına kaydedilmez. Sonuç yalnızca açık olan sayfada durur;
          sayfayı yenilediğinizde ya da kapattığınızda kaybolur.
        </li>
        <li>Render sunucu kayıtları, barındırma planına göre 7 ile 30 gün arasında saklanır ve sonra silinir.</li>
        <li>Groq ve Tavily&apos;deki saklama, yukarıda belirtildiği gibi bu şirketlerin kendi koşullarına bağlıdır.</li>
      </ul>

      <h2>Göndermemeniz gerekenler</h2>
      <p>
        Ad, telefon, adres, kimlik numarası gibi kişisel bilgiler; sağlık, din, siyasi görüş gibi özel nitelikli bilgiler
        ya da başka birine ait kişisel veriler içeren metin göndermeyin. Göndermeden önce bu bilgileri metinden çıkarın.
        Sonuçları kaydetmek isterseniz &quot;Yazdır / PDF kaydet&quot; ya da kopyalama seçeneğini kullanın; bunlar
        yalnızca sizin cihazınızda çalışır.
      </p>

      <h2>Haklarınız</h2>
      <p>KVKK&apos;nın 11. maddesine göre şu haklara sahipsiniz:</p>
      <ul>
        <li>kişisel verilerinizin işlenip işlenmediğini öğrenme ve işlendiyse bilgi isteme,</li>
        <li>işlenme amacını ve amaca uygun kullanılıp kullanılmadığını öğrenme,</li>
        <li>yurt içinde ya da yurt dışında aktarıldığı üçüncü kişileri bilme,</li>
        <li>eksik ya da yanlış işlenmişse düzeltilmesini, KVKK&apos;daki şartlar oluşmuşsa silinmesini isteme ve bu işlemlerin aktarıldığı kişilere bildirilmesini isteme,</li>
        <li>yalnızca otomatik sistemlerle analiz edilmesi sonucunda aleyhinize bir sonuç çıkmasına itiraz etme,</li>
        <li>kanuna aykırı işleme nedeniyle zarara uğrarsanız zararın giderilmesini isteme.</li>
      </ul>
      <p>
        Başvurularınızı <EmailLink /> adresine gönderebilirsiniz; başvurunuz en geç 30 gün içinde ücretsiz olarak
        yanıtlanır. Metinleri saklamadığımız için çoğu durumda size ait bir kayıt bulunmaz. Yanıtımızı yeterli bulmazsanız
        Kişisel Verileri Koruma Kurulu&apos;na şikâyette bulunabilirsiniz.
      </p>

      <h2>Değişiklikler</h2>
      <p>
        Bu politika değişirse güncel hâli bu sayfada, yeni tarihiyle yayımlanır. Hizmetin kullanım kuralları için{" "}
        <a href={TERMS_PATH}>kullanım koşullarına</a> bakın.
      </p>
    </LegalPage>
  );
}
