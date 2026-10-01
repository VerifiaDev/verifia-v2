import type { ErrorCode, InputMode, Verdict } from "./types";

export const VERDICT_ORDER: Verdict[] = ["SUPPORTED", "REFUTED", "CONFLICTING", "NOT_ENOUGH_EVIDENCE"];

export const VERDICT_META: Record<
  Verdict,
  { label: string; meaning: string; symbol: string; tone: "ok" | "bad" | "unknown" | "mixed" }
> = {
  SUPPORTED: {
    label: "Kanıtlar destekliyor",
    meaning: "Bulunan kaynaklar bu iddiayı doğruluyor.",
    symbol: "✓",
    tone: "ok",
  },
  REFUTED: {
    label: "Kanıtlar çelişiyor",
    meaning: "Bulunan kaynaklar bu iddiayla çelişiyor.",
    symbol: "✕",
    tone: "bad",
  },
  CONFLICTING: {
    label: "Kaynaklar birbiriyle çelişiyor",
    meaning: "Kaynaklar farklı sonuçlara varıyor ya da iddia seçmeci sunulmuş.",
    symbol: "≠",
    tone: "mixed",
  },
  NOT_ENOUGH_EVIDENCE: {
    label: "Yeterli kanıt yok",
    meaning: "İddiayı doğrulayacak ya da çürütecek yeterli kaynak bulunamadı. Bu, iddianın yanlış olduğu anlamına gelmez.",
    symbol: "?",
    tone: "unknown",
  },
};

/** Hata metinleri: ne oldu → kullanıcı şimdi ne yapabilir. */
export const ERROR_COPY: Record<ErrorCode, { title: string; what: string; todo: string[]; retry: boolean }> = {
  INVALID_INPUT: {
    title: "Girdi işlenemedi",
    what: "Gönderilen içerik geçerli bir girdi olarak kabul edilmedi.",
    todo: ["Metnin boş olmadığından emin olun.", "Bağlantıysa https:// ile başlayan tam adresi girin."],
    retry: false,
  },
  INPUT_TOO_LONG: {
    title: "Metin çok uzun",
    what: "Gönderdiğiniz metin, bir seferde incelenebilecek uzunluğu aşıyor.",
    todo: ["Yalnızca doğrulamak istediğiniz bölümü yapıştırın.", "Uzun metinleri birkaç parçada gönderin."],
    retry: false,
  },
  URL_UNREADABLE: {
    title: "Bağlantı okunamadı",
    what: "Bu adresteki sayfa açılamadı ya da içeriği okunamadı. Sayfa giriş gerektiriyor ya da erişime kapalı olabilir.",
    todo: [
      "Bağlantıyı tarayıcıda açıp çalıştığını kontrol edin.",
      "Haberin metnini kopyalayıp “Metin” sekmesinden gönderin.",
    ],
    retry: false,
  },
  IMAGE_UNREADABLE: {
    title: "Görsel işlenemedi",
    what: "Görseldeki yazı okunamadı.",
    todo: ["Daha yüksek çözünürlüklü bir görsel deneyin.", "Görseldeki metni yazıp “Metin” sekmesinden gönderin."],
    retry: false,
  },
  TIMEOUT: {
    title: "Analiz zaman aşımına uğradı",
    what: "Sunucu belirlenen sürede yanıt vermedi. Metin çok sayıda iddia içeriyor ya da sunucu yoğun olabilir.",
    todo: ["Aynı içeriği yeniden deneyin.", "Metni kısaltıp daha az iddiayla deneyin."],
    retry: true,
  },
  NETWORK: {
    title: "Sunucuya ulaşılamadı",
    what: "İstek sunucuya iletilemedi. İnternet bağlantınızda ya da sunucuda sorun olabilir.",
    todo: ["İnternet bağlantınızı kontrol edin.", "Birkaç saniye sonra yeniden deneyin."],
    retry: true,
  },
  INTERNAL_ERROR: {
    title: "Sunucuda bir hata oluştu",
    what: "Sistem isteği tamamlayamadı. Bu, girdinizden kaynaklanan bir sorun değil.",
    todo: ["Birkaç dakika sonra yeniden deneyin.", "Sorun sürerse içeriği saklayıp daha sonra tekrar gönderin."],
    retry: true,
  },
};

export const INPUT_MODES: { id: InputMode; label: string }[] = [
  { id: "text", label: "Metin" },
  { id: "url", label: "Bağlantı" },
];

const dateFmt = new Intl.DateTimeFormat("tr-TR", { day: "numeric", month: "long", year: "numeric" });

/** "2023-03-14" → "14 Mart 2023". Tarih yoksa ya da bozuksa null. */
export function formatDate(iso: string | null): string | null {
  if (!iso) return null;
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? null : dateFmt.format(d);
}

/** Kaynağın alan adı; kaynak adıyla birlikte, onun yerine değil. */
export function hostOf(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}

/** Yalnızca http/https bağlantılarına izin verir (javascript: vb. engellenir). */
export function isSafeHttpUrl(url: string): boolean {
  try {
    const p = new URL(url).protocol;
    return p === "http:" || p === "https:";
  } catch {
    return false;
  }
}

/** Kaynak listesindeki bir öğenin sayfa içi bağlantı kimliği. */
export function sourceAnchor(claimId: string, number: number): string {
  return `src-${claimId.replace(/[^A-Za-z0-9_-]/g, "_")}-${number}`;
}

export function claimAnchor(claimId: string): string {
  return `claim-${claimId.replace(/[^A-Za-z0-9_-]/g, "_")}`;
}
