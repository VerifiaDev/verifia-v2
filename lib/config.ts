/** Site adı ve sabitler tek yerde. Adı değiştirmek için sadece burayı düzenleyin. */
export const SITE_NAME = "verify";
export const SITE_TAGLINE = "Kanıtı görün. Kararı siz verin.";

/** Hazır örnek raporun kendi sayfası (app/ornek/apollo-11). Paylaşım bağlantısı ve site haritası burayı gösterir. */
export const SAMPLE_REPORT_PATH = "/ornek/apollo-11";

/** Örnek raporun paylaşılacak tam adresi; `origin` sitenin adresidir (tarayıcıda `window.location.origin`). */
export function sampleReportUrl(origin: string): string {
  return `${origin}${SAMPLE_REPORT_PATH}`;
}

/** Doldurulursa navbar ve footer'da "GitHub" bağlantısı görünür. Boşsa görünmez. */
export const REPO_URL = "";

/**
 * Arayüzün metin sınırı. Backend 10.000 karakter kabul eder (`max_length=10000`), ama arayüz bilerek daha azını
 * gönderir: 11 Ekim 2026'da canlıdaki backend hâlâ 1.0.0 sürümüydü (`GET /openapi.json`). O sürüm iddia sayısını ve
 * toplam süreyi sınırlamıyor, iddiaları sırayla işliyor; uzun metin arayüzün süre sınırını aşıyor ve sunucu işi
 * sürdürüp kota harcıyor.
 * backend_v2 (en çok 8 iddia, 45 saniye; fazlası "atlandı" olarak bildirilir) canlıya çıkınca 10_000'e yükseltilebilir;
 * önce `GET /openapi.json` içinde sürümün 2.0.0 olduğu doğrulanmalıdır.
 */
export const MAX_INPUT_LENGTH = 3_000;

/** Tek istek bu süreden uzun sürerse vazgeçilir (ms). Çok iddialı metinlerde uzun sürebilir. */
export const REQUEST_TIMEOUT_MS = 90_000;

/**
 * İncelemeden önce sunucunun `/health` yanıtı en fazla bu kadar beklenir (ms). Uyuyan bir sunucunun
 * uyanmasına yetecek kadar uzun olmalı: 11 Ekim 2026'da canlıda ilk yanıt yaklaşık 132 saniyede geldi; eski
 * 60 saniyelik sınır bu süreyi karşılamıyordu. Sayfa açılınca gönderilen ön ısıtma
 * isteği sayesinde kullanıcı çoğu zaman bu sürenin tamamını beklemez. Sunucu daha hızlı açılır hâle gelince
 * (backend_v2, sürekli açık plan) düşürülmelidir: kilitli bir sunucuda kullanıcı bu kadar bekletilir.
 */
export const HEALTH_TIMEOUT_MS = 150_000;

/** Sağlık yanıtı bu kadar gecikirse (ms) kullanıcıya "inceleniyor" değil "sunucunun yanıtı bekleniyor" denir. */
export const SERVER_WAIT_NOTICE_MS = 5_000;

export const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "";

/** Navbar ve footer'daki sayfa içi bağlantılar. Tek yerden yönetilir. */
export const SITE_LINKS = [
  { href: "#analyzer", label: "İncele" },
  { href: "#nasil", label: "Nasıl çalışır?" },
  { href: "#guven", label: "Güven ilkeleri" },
];
