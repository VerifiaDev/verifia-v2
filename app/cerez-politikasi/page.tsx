import type { Metadata } from "next";
import { EmailLink, ExternalLink, LegalPage } from "@/components/LegalPage";
import { COOKIES_PATH, LEGAL_COMPLETE, PRIVACY_PATH, PROVIDERS } from "@/lib/legal";
import { SITE_NAME } from "@/lib/config";
import { SITE_ORIGIN } from "@/lib/site";

export const metadata: Metadata = {
  title: `Çerez politikası | ${SITE_NAME}`,
  description: "verify çerez kullanmaz. Tarayıcınızda saklanan tek bilgi, sizin seçtiğiniz tema tercihidir.",
  ...(SITE_ORIGIN ? { alternates: { canonical: COOKIES_PATH } } : {}),
  ...(LEGAL_COMPLETE ? {} : { robots: { index: false, follow: false } }),
};

/**
 * Koddan doğrulanabilir (16 Ekim 2026): sitede document.cookie yok; tek tarayıcı kaydı components/ThemeToggle.tsx
 * içindeki localStorage "verify-theme" anahtarıdır ve yalnızca düğmeye basınca yazılır. Yazı tipleri app/fonts'tan
 * sunulur; dış betik, iframe ya da analitik paketi yoktur (package.json, next.config.ts içindeki CSP).
 * Bunlardan biri değişirse bu sayfa ve tests/legal.test.tsx güncellenmelidir.
 */
export default function CookiesPage() {
  return (
    <LegalPage title="Çerez politikası" path={COOKIES_PATH}>
      <p>
        Çerezler, web sitelerinin tarayıcınıza kaydettiği küçük dosyalardır; çoğu zaman ziyaretçileri tanımak ya da
        izlemek için kullanılır. Bu sayfa, verify&apos;ın tarayıcınızda neyi sakladığını anlatır.
      </p>

      <h2>verify çerez kullanmaz</h2>
      <ul>
        <li>Ziyaretçi analizi (analitik), reklam ya da izleme aracı kullanılmaz.</li>
        <li>Sosyal medya düğmesi, video, harita gibi başka sitelerden yüklenen içerik yoktur.</li>
        <li>Yazı tipleri ve görseller sitenin kendisinden yüklenir; ziyaretiniz üçüncü bir siteye bildirilmez.</li>
        <li>İnceleme sunucusuna yapılan istekler çerez taşımaz.</li>
      </ul>

      <h2>Tarayıcınızda saklanan tek bilgi: tema tercihi</h2>
      <p>
        Gece modu düğmesine bastığınızda seçiminiz (açık ya da koyu) tarayıcınızın yerel depolama alanına
        (localStorage) <code>verify-theme</code> adıyla kaydedilir. Böylece sayfayı yeniden açtığınızda aynı görünüm
        gelir.
      </p>
      <ul>
        <li>Yalnızca siz düğmeye bastığınızda kaydedilir. Düğmeye hiç basmazsanız hiçbir şey kaydedilmez ve cihazınızın ayarı kullanılır.</li>
        <li>Bize ya da başka bir yere gönderilmez; sizi tanımlamaz.</li>
        <li>
          Silmek için tarayıcınızın ayarlarından bu sitenin verilerini temizleyebilirsiniz. Sonrasında site yine
          cihazınızın açık ya da koyu ayarını izler.
        </li>
      </ul>

      <h2>Neden çerez onayı istemiyoruz?</h2>
      <p>
        Sizi tanıyan ya da izleyen bir çerez kullanmadığımız için çerez onay penceresi göstermiyoruz. Tema tercihi
        yalnızca sizin isteğinizle ve sizin istediğiniz görünümü korumak için kaydedilir. İleride analitik ya da çerez
        eklenirse önce bu sayfa güncellenir ve gerekiyorsa onayınız istenir.
      </p>

      <h2>Barındırma hizmeti</h2>
      <p>
        Site {PROVIDERS.vercel.name} üzerinde barındırılır. Siteyi açtığınızda bağlantıya ait teknik bilgiler (ör. IP
        adresi) Vercel tarafından işlenir; ayrıntılar <a href={PRIVACY_PATH}>gizlilik politikasında</a> ve{" "}
        <ExternalLink href={PROVIDERS.vercel.policy}>Vercel gizlilik bildiriminde</ExternalLink>.
      </p>

      <h2>İletişim</h2>
      <p>
        Sorularınız için: <EmailLink />
      </p>
    </LegalPage>
  );
}
