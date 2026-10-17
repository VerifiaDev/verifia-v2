# Rapor tasarımı — yayın onayı bekleniyor

8 Ekim 2026. Bu çalışma yalnızca yerelde hazırlanmıştır; yayın veya Git push yapılmadı.

## Hazır olanlar

- Önceden hazırlanmış Apollo 11 örneği: kaynak bağlantıları NASA'ya gider; eğitim metni gerçek bir haber olarak sunulmaz.
- Kısa değerlendirme, incelenen metin, hazırlama tarihi, iddia bazında sonuçlar, kaynak rolü ve yöntem/sınırlamalar.
- Kanıt pasajları doğrudan alıntı yerine açıkça Türkçe özet olarak etiketlenir.
- Kaynaklar aynı kuruma ait olduğundan bağımsız doğrulama sayılmadığı belirtilir.
- Rapor kopyalama, yazdırma/PDF kaydetme ve yalnızca sabit örneği açan paylaşım bağlantısı.
- Kopyalama engellenirse otomatik odaklanan ve seçilebilir metin alanı. Gerçek bir iletişim kanalı olmayan geri bildirim taslağı kaldırıldı.
- Gizlilik bölümü: kesinleşmemiş saklama koşulları hakkında vaat verilmez.
- HTTP 429 için ayrı kullanım sınırı mesajı.

## Backend ile netleştirilecekler

1. `used_sources` kimliklerinin anlamı. Anlam kesinleşmeden kaynak ilişkileri bundan veya verdict değerinden tahmin edilmemeli.
2. Canlı sonuçlar için kaynak rolü (`supports`, `contradicts`, `context`), kaynak türü, pasaj türü ve rapor kapsamı. Adaptör artık bu isteğe bağlı alanları okuyor; backend'in alanları gerçekten sağlayacağı doğrulanmalı. Eksik değerler tahmin edilmiyor.
3. Yanıt süresi (şu an 90 saniye; ayrıca 150 saniyeye kadar sunucu denetimi). Arayüz metin sınırı 3.000 (backend 10.000 kabul eder; backend_v2 canlıya çıkana kadar düşük tutulur).
4. URL desteği, CORS ve kısmi hata biçimi.
5. Saklama süresi, sağlayıcılar, silme yöntemi ve gerçek bildirim kanalı.
6. Şu an yalnızca hazır örnek bağlantısı paylaşılır; canlı sonuçlar saklanmaz. Rapor saklama yeni bir özellik olarak bu çalışmanın kapsamına alınmadı.

## Audit sonrası tamamlanan frontend düzeltmeleri

- Haber yapıştırma alanı ana sayfada görünür ve düzenlenebilir. API yokken gönderim yapılmaz; durum açıkça belirtilir.
- Tanıtım turu ve tekrar eden metinler azaltıldı. Özet ve incelenen metin isteğe bağlı açılır; rapor araçları kanıtlardan sonra gelir.
- Kapalı iddialarda da örnek etiketi kalır. Kaynak veya gerekçe eksikliği kart başlığında görünür.
- İddia listesine dönüş listeyi açar. Doğrudan kaynak bağlantıları ilgili iddiayı açar, odağı kaynağa taşır. Örneği kapatmak URL parametresini temizler ve giriş metnini korur.
- Uzun kanıt pasajları açılıp kapatılabilir. Eşleşmeyen kaynak atıfları açıklanır; aynı gruptaki geçerli bağlantılar korunur.
- Kopyalanan raporda atıf numaraları kaynak listesiyle eşleşir. Kopyalama başarısı ve engellenmesi için ayrı geri bildirim vardır.
- Tablet yan sütunu 1200 piksele ertelendi; mobil sonuç açıklamaları raporun başına taşındı. Alt menü dokunma alanları büyütüldü.
- Karakter sınırı ekran okuyucuya durum değişince duyurulur. Form, hata metinleri ve gizlilik açıklamaları mevcut davranışla uyumlu hâle getirildi.
- Yazdırma stilleri düzeltildi; kapalı rapor ayrıntılarını yazdırma öncesi açan ve sonra eski durumuna döndüren işlem eklendi.

## Doğrulama ve açık kalanlar

- Ana sayfa ve örnek rapor 320, 375, 390, 414, 768, 1024, 1280, 1440 ve 1920 pikselde kontrol edildi; yatay sayfa taşması bulunmadı.
- Tarayıcıda metin koruma, örnek açma/kapatma, kaynak odağı, iddia listesi, kopyalama bildirimi, karakter sınırı, boş giriş, iptal, zaman aşımı, boş sonuç ve kısmi sonuç kontrol edildi. Servis durumları yerel mock ile sınandı; canlı backend doğrulanmadı.
- Production derlemesi ve 126 otomatik test başarılı. Açık/koyu tema kontrast testleri de bu grupta.
- Gerçek cihazlarda Safari/Firefox, ekran okuyucu ve PDF çıktısı için son kabul kontrolü gerekiyor; bu kontroller tamamlanmış sayılmıyor.
- Gerçek API, veri saklama/silme koşulları ve ulaşılabilir iletişim/düzeltme kanalı eksik. Frontend bu bilgileri uydurmuyor.
- Yerel derlemede yayın alan adı olmadığı için metadataBase uyarısı var. Vercel ortamındaki üretim alan adı, canonical ve paylaşım görselleri yayın öncesi kontrol edilmeli.
- Yayın yapılmadı; son tasarım için kullanıcı onayı gerekiyor.

## Onay kapsamı

Rapor tasarımı 8 Ekim 2026'da kullanıcı onayıyla yayına alındı ve canlı inceleme servisine (Render) bağlı çalışıyor. Hazır örnek rapor canlı sitede de sunulur (ana sayfadaki düğme ve `/ornek/apollo-11`).
