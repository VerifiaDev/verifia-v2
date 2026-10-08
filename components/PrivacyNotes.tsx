import { Section } from "./Section";
import { apiInfo } from "@/lib/api";

export function PrivacyNotes() {
  return <Section id="gizlilik" title="İçeriğiniz ve gizlilik">
    <div className="privacy-grid">
      <div><h3 className="t-h4">{apiInfo.unavailable || apiInfo.usingMock ? "Metniniz gönderilmez" : "Metniniz inceleme servisine gönderilir"}</h3><p className="muted">{apiInfo.unavailable || apiInfo.usingMock ? "Bu sürümde yazdığınız metin inceleme API’sine gönderilmez." : "İncelemeyi başlat seçeneği, eklediğiniz içeriği analiz için servise iletir. Kişisel veya gizli bilgileri göndermeden önce çıkarın."} Arayüz metinleri ve sonuçları kalıcı olarak kaydetmez; sayfa yenilendiğinde kaybolurlar. Tema tercihi tarayıcıda saklanır.</p></div>
      <div><h3 className="t-h4">Örnek rapor ve veri koşulları</h3><p className="muted">Hazır örnek rapor yazdığınız metni kullanmaz. Kopyalama ve yazdırma tarayıcınızda çalışır; örnek bağlantısı kişisel içerik taşımaz. Canlı servisin saklama süresi, hizmet sağlayıcıları ve silme yöntemi henüz açıklanmadı.</p></div>
    </div>
  </Section>;
}
