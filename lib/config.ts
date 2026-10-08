/** Site adı ve sabitler tek yerde. Adı değiştirmek için sadece burayı düzenleyin. */
export const SITE_NAME = "verify";
export const SITE_TAGLINE = "Kanıtı görün. Kararı siz verin.";

/** Doldurulursa navbar ve footer'da "GitHub" bağlantısı görünür. Boşsa görünmez. */
export const REPO_URL = "";

/**
 * Arayüzün metin sınırı. Backend 10.000 karaktere kadar kabul ediyor (backend/main.py, `max_length=10000`);
 * arayüz bilerek daha düşük tutar: uzun metin daha çok iddia, daha uzun bekleme ve daha çok dış servis
 * kotası demek (docs/SECURITY_AUDIT.md, K1-K2). Backend sınırının altında kaldığı sürece güvenle değiştirilebilir.
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
