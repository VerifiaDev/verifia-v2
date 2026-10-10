/** Site adı ve sabitler tek yerde. Adı değiştirmek için sadece burayı düzenleyin. */
export const SITE_NAME = "verify";
export const SITE_TAGLINE = "Kanıtı görün. Kararı siz verin.";

/** Doldurulursa navbar ve footer'da "GitHub" bağlantısı görünür. Boşsa görünmez. */
export const REPO_URL = "";

/**
 * Arayüzün metin sınırı = backend'in kabul ettiği sınır (backend_v2/app/main.py, `max_length=10000`).
 * Backend sınırı değişirse burası da değişmelidir; bunun üstü sunucuda 422 (VALIDATION_ERROR) olur.
 * Not: uzun metin daha çok iddia demektir. Backend en çok 8 iddiayı inceler, kalanı "atlandı" olarak bildirir
 * ve toplam süreyi 45 saniyeyle sınırlar; arayüz bunları "İncelenemeyen iddialar" bölümünde gösterir.
 */
export const MAX_INPUT_LENGTH = 10_000;

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
