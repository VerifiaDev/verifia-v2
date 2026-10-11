import type { Metadata } from "next";
import { EmailLink, Fill, LegalPage } from "@/components/LegalPage";
import { LEGAL, LEGAL_COMPLETE, PRIVACY_PATH } from "@/lib/legal";
import { SITE_NAME } from "@/lib/config";
import { SITE_ORIGIN } from "@/lib/site";

export const metadata: Metadata = {
  title: `Gizlilik politikası | ${SITE_NAME}`,
  description: "verify'a gönderdiğiniz metnin nasıl işlendiği, kimlere iletildiği ve haklarınız.",
  ...(SITE_ORIGIN ? { alternates: { canonical: PRIVACY_PATH } } : {}),
  ...(LEGAL_COMPLETE ? {} : { robots: { index: false, follow: false } }),
};

/**
 * İçerik, sitenin ve backend'in koddan doğrulanabilen davranışına dayanır (lib/api, backend/main.py):
 * metin saklanmaz, çerez ve analitik yoktur, metin Groq'a ve iddialar Tavily'ye gider. Bilinmeyen bilgiler
 * lib/legal.ts'ten gelir. Hukuki metin değildir; yayından önce hukukçu kontrolü önerilir.
 */
export default function PrivacyPage() {
  return (
    <LegalPage title="Gizlilik politikası" other="terms">
      <p>
        Bu sayfa, verify&apos;a incelemek için gönderdiğiniz içeriğin nasıl işlendiğini anlatır. verify bir hesap
        sistemi kullanmaz; adınızı, e-posta adresinizi ya da başka bir kimlik bilginizi istemez.
      </p>

      <h2>Veri sorumlusu</h2>
      <p>
        <Fill value={LEGAL.owner} label="sitenin sorumlusu (kişi ya da ekip adı)" />. İletişim: <EmailLink />
      </p>

      <h2>Hangi veriler işlenir?</h2>
      <ul>
        <li>İncelemek için yapıştırdığınız metin.</li>
        <li>
          Bağlantı sırasında tarayıcınızın gönderdiği teknik bilgiler (IP adresi, tarayıcı türü, istek zamanı). Bunlar
          sitenin ve sunucunun barındırma sağlayıcıları tarafından işlenir.
        </li>
        <li>
          Tema tercihiniz (açık ya da koyu) yalnızca kendi tarayıcınızda saklanır ve bize gönderilmez.
        </li>
      </ul>
      <p>Çerez, reklam ya da ziyaretçi analizi (analitik) kullanılmaz.</p>

      <h2>Neden işlenir?</h2>
      <p>
        Metindeki kontrol edilebilir iddiaları ayırmak, her iddia için web&apos;de kaynak aramak ve sonucu size göstermek
        için. Teknik bilgiler, hizmetin çalışması ve kötüye kullanıma karşı korunması için gereklidir.
      </p>

      <h2>Veriler kimlere iletilir?</h2>
      <ul>
        <li>
          <strong>Render:</strong> inceleme sunucumuzun barındırıldığı hizmet. Metniniz önce buraya gönderilir.
        </li>
        <li>
          <strong>Groq:</strong> metnin tamamı, iddiaları ayıran ve kaynaklara göre değerlendiren yapay zekâ modeline
          iletilir.
        </li>
        <li>
          <strong>Tavily:</strong> ayrılan iddialar, kaynak bulmak için web araması sorgusu olarak iletilir.
        </li>
        <li>
          <strong>Vercel:</strong> sitenin kendisinin barındırıldığı hizmet.
        </li>
      </ul>
      <p>
        Arama sonucunda bulunan sayfalar sunucumuz tarafından açılır; bu sitelere metniniz gönderilmez. Yukarıdaki hizmet
        sağlayıcıları yurt dışındadır; içeriği kendi koşullarına göre işlerler.
      </p>

      <h2>Ne kadar saklanır?</h2>
      <p>
        Metniniz ve inceleme sonuçlarınız tarafımızdan bir veritabanına kaydedilmez; sayfayı yenilediğinizde kaybolur.
        Sunucu kayıtları <Fill value={LEGAL.logRetention} label="sunucu kayıtlarının saklama süresi" /> boyunca tutulur.
      </p>

      <h2>Göndermemeniz gerekenler</h2>
      <p>
        Ad, telefon, adres, kimlik numarası; sağlık, din, siyasi görüş gibi özel nitelikli bilgiler ya da başka birine ait
        kişisel veriler içeren metin göndermeyin. Göndermeden önce bu bilgileri metinden çıkarın.
      </p>

      <h2>Haklarınız</h2>
      <p>
        6698 sayılı Kişisel Verilerin Korunması Kanunu&apos;nun 11. maddesi kapsamında verilerinizin işlenip
        işlenmediğini öğrenme, bilgi isteme, düzeltilmesini ya da silinmesini isteme ve işlemeye itiraz etme haklarınız
        vardır. Başvurularınız için: <EmailLink />
      </p>

      <h2>Değişiklikler</h2>
      <p>Bu politika değişirse güncel hâli bu sayfada, yeni tarihiyle yayımlanır.</p>
    </LegalPage>
  );
}
