/** Site adı ve sabitler tek yerde. Adı değiştirmek için sadece burayı düzenleyin. */
export const SITE_NAME = "Verifia";
export const SITE_TAGLINE = "Kanıtı görün. Kararı siz verin.";

/** Doldurulursa navbar ve footer'da "GitHub" bağlantısı görünür. Boşsa görünmez. */
export const REPO_URL = "";

/** VARSAYIM: backend ekibi gerçek sınırı söyleyene kadar. */
export const MAX_INPUT_LENGTH = 5000;

/** Tek istek bu süreden uzun sürerse vazgeçilir (ms). Çok iddialı metinlerde uzun sürebilir. */
export const REQUEST_TIMEOUT_MS = 90_000;

export const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "";

/** Navbar ve footer'daki sayfa içi bağlantılar. Tek yerden yönetilir. */
export const SITE_LINKS = [
  { href: "#analyzer", label: "İncele" },
  { href: "#nasil", label: "Nasıl çalışır?" },
  { href: "#guven", label: "Güven ilkeleri" },
];
