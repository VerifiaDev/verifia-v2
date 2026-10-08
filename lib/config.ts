/** Site adı ve sabitler tek yerde. Adı değiştirmek için sadece burayı düzenleyin. */
export const SITE_NAME = "verify";
export const SITE_TAGLINE = "Kanıtı görün. Kararı siz verin.";

/** Doldurulursa navbar ve footer'da "GitHub" bağlantısı görünür. Boşsa görünmez. */
export const REPO_URL = "";

/** backend/main.py: VerifyRequest.text max_length=10000 (Python karakter sayar; JS UTF-16 birimi sayar, yani bu sınır en kötü ihtimalle biraz erken keser). */
export const MAX_INPUT_LENGTH = 10_000;

/** Tek istek bu süreden uzun sürerse vazgeçilir (ms). Çok iddialı metinlerde uzun sürebilir. */
export const REQUEST_TIMEOUT_MS = 90_000;

export const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "";

/** Navbar ve footer'daki sayfa içi bağlantılar. Tek yerden yönetilir. */
export const SITE_LINKS = [
  { href: "#analyzer", label: "İncele" },
  { href: "#nasil", label: "Nasıl çalışır?" },
  { href: "#guven", label: "Güven ilkeleri" },
];
