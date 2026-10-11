/** Site adı ve sabitler tek yerde. Adı değiştirmek için sadece burayı düzenleyin. */
export const SITE_NAME = "verify";
export const SITE_TAGLINE = "Kanıtı görün. Kararı siz verin.";

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
 * uyanmasına yetecek kadar uzun; kilitli bir sunucuya pahalı inceleme isteğini yığmayacak kadar kısa.
 */
export const HEALTH_TIMEOUT_MS = 60_000;

export const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "";

/** Navbar ve footer'daki sayfa içi bağlantılar. Tek yerden yönetilir. */
export const SITE_LINKS = [
  { href: "#analyzer", label: "İncele" },
  { href: "#nasil", label: "Nasıl çalışır?" },
  { href: "#guven", label: "Güven ilkeleri" },
];
