/** Site adı ve sabitler tek yerde. Adı değiştirmek için sadece burayı düzenleyin. */
export const SITE_NAME = "verify";
export const SITE_TAGLINE = "Bize güvenme, kanıtlara bak.";

/** Doldurulursa navbar ve footer'da "GitHub" bağlantısı görünür. Boşsa görünmez. */
export const REPO_URL = "";

/** VARSAYIM: backend ekibi gerçek sınırı söyleyene kadar. */
export const MAX_INPUT_LENGTH = 5000;

/** Tek istek bu süreden uzun sürerse vazgeçilir (ms). Çok iddialı metinlerde uzun sürebilir. */
export const REQUEST_TIMEOUT_MS = 90_000;

export const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "";
export const USING_MOCK = API_BASE_URL === "";
