import { Section } from "./Section";
import { apiInfo } from "@/lib/api";

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
            Arayüz metinleri ve sonuçları kalıcı olarak kaydetmez; sayfa yenilendiğinde kaybolurlar. Tema tercihi
            tarayıcıda saklanır.
          </p>
        </div>
        <div>
          <h3 className="t-h4">Örnek rapor ve veri koşulları</h3>
          <p className="muted">
            Hazır örnek rapor yazdığınız metni kullanmaz. Kopyalama ve yazdırma tarayıcınızda çalışır; örnek bağlantısı
            kişisel içerik taşımaz. Canlı servisin saklama süresi, hizmet sağlayıcıları ve silme yöntemi henüz
            açıklanmadı.
          </p>
        </div>
      </div>
    </Section>
  );
}
