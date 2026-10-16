import { Section } from "./Section";
import { apiInfo } from "@/lib/api";
import { COOKIES_PATH, LEGAL_COMPLETE, PRIVACY_PATH } from "@/lib/legal";

/** Gönderim yoksa (servis bağlı değil ya da geliştirmedeki örnek veri) metin hiçbir yere gitmez. */
const sendsText = !(apiInfo.unavailable || apiInfo.usingMock);

export function PrivacyNotes() {
  return (
    <Section id="gizlilik" title="İçeriğiniz ve gizlilik">
      <div className="privacy-grid">
        <div>
          <h3 className="t-h4">{sendsText ? "Metniniz inceleme servisine gönderilir" : "Metniniz gönderilmez"}</h3>
          <p className="muted">
            {sendsText
              ? "İncelemeyi başlat seçeneği, eklediğiniz içeriği analiz için servise iletir; servis içeriği yapay zekâ modeli ve web araması yapan dış servislere gönderir. Kişisel veya gizli bilgileri göndermeden önce çıkarın."
              : "Bu sürümde yazdığınız metin inceleme API’sine gönderilmez."}{" "}
            Metinler ve sonuçlar bir veritabanına kaydedilmez; sayfa yenilendiğinde kaybolurlar. Gece modu düğmesine
            basarsanız tema tercihiniz yalnızca kendi tarayıcınızda saklanır.
          </p>
        </div>
        <div>
          <h3 className="t-h4">Kimler görür, ne kadar saklanır?</h3>
          <p className="muted">
            {sendsText
              ? "Metniniz Render'daki inceleme sunucumuza, oradan Groq'un yapay zekâ modeline gider; iddialardan üretilen arama sorguları Tavily'ye gönderilir. Bu servisler yurt dışındadır. Sunucu kayıtları IP adresinizi ve arama sorgularını içerebilir ve en çok 30 gün saklanır. "
              : ""}
            Çerez, analitik ve reklam kullanılmaz. Hazır örnek rapor yazdığınız metni kullanmaz; kopyalama ve yazdırma
            yalnızca tarayıcınızda çalışır.
            {LEGAL_COMPLETE && (
              <>
                {" "}
                Ayrıntılar: <a href={PRIVACY_PATH}>gizlilik politikası</a>, <a href={COOKIES_PATH}>çerez politikası</a>.
              </>
            )}
          </p>
        </div>
      </div>
    </Section>
  );
}
