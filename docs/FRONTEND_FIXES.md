# Frontend bakım notları

`codex/frontend-quality` dalındaki düzeltmeler, depo kök dizine taşındıktan sonra yeni yapıya uygulanmıştır.

## Hata dayanıklılığı

- Bozuk API satırları geçerli sonuçları düşürmeden ayrılır.
- Geçersiz kaynak adresleri kanıt sayımına alınmaz.
- Bilinmeyen işlem durumları sonuç olarak gösterilmez.
- Tekrarlanan iddia kimlikleri ve özel karakterler bağlantı çakışmasına yol açmaz.
- Geçersiz takvim günleri tarih olarak gösterilmez.
- Sağlık hataları, iptal ve yanıt gövdesi zaman aşımı ayrı ele alınır.

## Arayüz

Tema ve hareket tercihleri dış kaynak abonelikleriyle (`useSyncExternalStore`) izlenir. Örnek gösterimi, kısa ekranlarda animasyon başlamasını beklerken içeriği gizlemez. Renk, tipografi ve boşluk sistemi korunur.

## Doğrulama

Lint, TypeScript, birim/bileşen testleri ve üretim derlemesi `.github/workflows/ci.yml` iş akışının parçalarıdır. Yerel doğrulamada 198 test başarılıdır (`tests/frontend-resilience.test.ts` dahil).

Gerçek sağlayıcılara bağlanan uçtan uca analiz bu değişiklik kapsamında çalıştırılmadı. Backend tarafında benzersiz kaynak kimlikleri ve istemci iptalinden sonra sunucu işleminin davranışı ayrıca doğrulanmalıdır.
