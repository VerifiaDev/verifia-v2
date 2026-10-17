import type { ErrorCode, InputMode, Verdict } from "./types";

export const VERDICT_ORDER: Verdict[] = ["SUPPORTED", "REFUTED", "CONFLICTING", "NOT_ENOUGH_EVIDENCE"];

/** Sonuç simgeleri (components/Icon.tsx içindeki çizimlerin adları). */
export type VerdictIcon = "check" | "cross" | "not-equal" | "question";

/**
 * `meaning`: sonucun açıklaması; "Sonuç türleri" listesinde gösterilir.
 * `caveat`: sonucun yanlış okunmasını önleyen uyarı; sonuç kutusunda etiketin altında gösterilir.
 * Sonuç kutusunda `meaning` yinelenmez (etiketin aynısını söylerdi); yalnızca uyarısı olan sonuçta not çıkar.
 */
export const VERDICT_META: Record<
  Verdict,
  { label: string; meaning: string; caveat?: string; icon: VerdictIcon; tone: "ok" | "bad" | "unknown" | "mixed" }
> = {
  SUPPORTED: {
    label: "Kanıtlar destekliyor",
    meaning: "Bulunan kaynaklar bu iddiayı destekliyor.",
    icon: "check",
    tone: "ok",
  },
  REFUTED: {
    label: "Kanıtlar iddiayla çelişiyor",
    meaning: "Bulunan kaynaklar bu iddiayla çelişiyor.",
    icon: "cross",
    tone: "bad",
  },
  CONFLICTING: {
    label: "Kaynaklar birbiriyle çelişiyor",
    meaning: "Bulunan kaynaklar aynı iddia hakkında birbiriyle uyuşmayan bilgiler veriyor. Ayrıntı ve bağlamı gerekçede inceleyin.",
    icon: "not-equal",
    tone: "mixed",
  },
  NOT_ENOUGH_EVIDENCE: {
    label: "Yeterli kanıt yok",
    meaning: "İddiayı doğrulayacak ya da çürütecek yeterli kaynak bulunamadı. Bu, iddianın yanlış olduğu anlamına gelmez.",
    caveat: "Bu, iddianın yanlış olduğu anlamına gelmez.",
    icon: "question",
    tone: "unknown",
  },
};

/** Hata metinleri: ne oldu → kullanıcı şimdi ne yapabilir. */
export const ERROR_COPY: Record<ErrorCode, { title: string; what: string; todo: string[]; retry: boolean }> = {
  RATE_LIMITED: {
    title: "İstek sınırına ulaşıldı",
    what: "Kısa sürede gönderilebilecek inceleme sayısı aşıldı. Yazdığınız içerik yerinde duruyor.",
    todo: ["Biraz bekledikten sonra yeniden deneyin."],
    retry: true,
  },
  INVALID_INPUT: {
    title: "Girdi işlenemedi",
    what: "Gönderilen içerik geçerli bir girdi olarak kabul edilmedi.",
    todo: ["Metnin boş olmadığından emin olun.", "İncelenecek haber metnini veya somut bir iddiayı giriş alanına ekleyin."],
    retry: false,
  },
  INPUT_TOO_LONG: {
    title: "Metin çok uzun",
    what: "Gönderdiğiniz metin, bir seferde incelenebilecek uzunluğu aşıyor.",
    todo: ["Yalnızca incelenmesini istediğiniz bölümü yapıştırın.", "Uzun metinleri birkaç parçada gönderin."],
    retry: false,
  },
  URL_UNREADABLE: {
    title: "Bağlantı okunamadı",
    what: "Bu adresteki sayfa açılamadı ya da içeriği okunamadı. Sayfa giriş gerektiriyor ya da erişime kapalı olabilir.",
    todo: [
      "Bağlantıyı tarayıcıda açıp çalıştığını kontrol edin.",
      "Haberin metnini kopyalayıp metin giriş alanından gönderin.",
    ],
    retry: false,
  },
  URL_UNSUPPORTED: {
    title: "Bağlantıyla inceleme henüz desteklenmiyor",
    what: "İnceleme servisi şu an yalnızca metin kabul ediyor. Gönderdiğiniz bağlantıdaki sayfa okunmadı ve incelenmedi.",
    todo: ["Haberin metnini kopyalayıp metin giriş alanından gönderin."],
    retry: false,
  },
  IMAGE_UNREADABLE: {
    title: "Görsel işlenemedi",
    what: "Görseldeki yazı okunamadı.",
    todo: ["Görseldeki iddiayı metin olarak yazıp giriş alanından gönderin."],
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
  OFFLINE: {
    title: "İnternet bağlantısı yok",
    what: "Cihazınız çevrimdışı görünüyor; istek gönderilemedi. Yazdığınız içerik yerinde duruyor.",
    todo: ["Bağlantınız geri gelince yeniden deneyin."],
    retry: true,
  },
  SERVER_BUSY: {
    title: "Sunucu şu an yanıt vermiyor",
    what: "İnceleme sunucusu başka bir incelemeyle meşgul ya da yeniden başlıyor olabilir. İçeriğiniz incelenmedi; yazdığınız metin yerinde duruyor.",
    todo: ["Birkaç dakika sonra yeniden deneyin."],
    retry: true,
  },
  QUOTA_EXCEEDED: {
    title: "Bugünkü inceleme sınırı doldu",
    what: "Sistemin günlük toplam inceleme sınırına ulaşıldı. İçeriğiniz incelenmedi.",
    todo: ["Yarın yeniden deneyin."],
    retry: false,
  },
  SERVICE_UNAVAILABLE: {
    title: "İnceleme servisi geçici olarak kullanılamıyor",
    what: "Arama ya da yapay zekâ servislerinden biri şu an yanıt vermiyor. Bu, girdinizden kaynaklanan bir sorun değil.",
    todo: ["Birkaç dakika sonra yeniden deneyin."],
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

/** 0.91 → "%91" (Türkçe yazım). */
export function formatPercent(ratio: number): string {
  return `%${Math.round(ratio * 100)}`;
}

const DATE_PARTS = { day: "numeric", month: "long", year: "numeric" } as const;
const dateFmt = new Intl.DateTimeFormat("tr-TR", DATE_PARTS);
const dateFmtUtc = new Intl.DateTimeFormat("tr-TR", { ...DATE_PARTS, timeZone: "UTC" });
const DATE_ONLY = /^\d{4}-\d{2}-\d{2}$/;
/** ISO 8601 tarih-saat: 2026-10-05T12:00:00Z, 2026-10-05T15:30:00+03:00, 2026-10-05 12:00 */
const ISO_DATE_TIME = /^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(:\d{2}(\.\d+)?)?(Z|[+-]\d{2}:?\d{2})?$/;
/** RFC 2822 (haber kaynaklarının ve arama servislerinin yaygın biçimi): Mon, 05 Oct 2026 12:00:00 GMT */
const RFC_2822 = /^([A-Za-z]{3},\s*)?\d{1,2}\s+[A-Za-z]{3}\s+\d{4}\s+\d{2}:\d{2}(:\d{2})?(\s*(GMT|UTC|Z|[+-]\d{4}))?$/;

/**
 * "2023-03-14" → "14 Mart 2023". Tarih yoksa ya da bozuksa null.
 * Yalnızca tarih içeren değer (saat yok) UTC gece yarısı sayılır; okuyanın saat diliminde gösterilirse
 * UTC'nin batısında bir gün geri kayar. Bu yüzden o biçim UTC'de yazılır.
 * Yalnızca gün ve ayı kesin olan biçimler okunur. "05.10.2026" gibi değerleri JavaScript ay/gün sırasıyla
 * yorumlayıp yanlış ama inandırıcı bir tarih üretir; bunlar tahmin edilmez, gösterilmez.
 */
export function formatDate(iso: string | null): string | null {
  if (!iso) return null;
  const value = iso.trim();
  const dateOnly = DATE_ONLY.test(value);
  if (!dateOnly && !ISO_DATE_TIME.test(value) && !RFC_2822.test(value)) return null;
  // Date silently normalizes impossible days (e.g. February 30) into the next month.
  const isoParts = /^(\d{4})-(\d{2})-(\d{2})/.exec(value);
  const rfcParts = /^(?:[A-Za-z]{3},\s*)?(\d{1,2})\s+([A-Za-z]{3})\s+(\d{4})/.exec(value);
  const months = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"];
  const year = Number(isoParts?.[1] ?? rfcParts?.[3]);
  const month = isoParts ? Number(isoParts[2]) : months.indexOf(rfcParts?.[2].toLowerCase() ?? "") + 1;
  const day = Number(isoParts?.[3] ?? rfcParts?.[1]);
  const leap = year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0);
  const days = [31, leap ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
  if (month < 1 || month > 12 || day < 1 || day > days[month - 1]) return null;
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return null;
  return (dateOnly ? dateFmtUtc : dateFmt).format(d);
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
  return `src-${anchorId(claimId)}-${number}`;
}

/** İddia listesinin (sonucun başındaki özet) sayfa içi adresi; her iddiadaki "listeye dön" bağlantısı buraya gider. */
export const CLAIM_LIST_ID = "iddia-listesi";

export function claimAnchor(claimId: string): string {
  return `claim-${anchorId(claimId)}`;
}

/** Escape each non-ASCII-safe character without collapsing distinct IDs. */
function anchorId(id: string): string {
  return Array.from(id, (char) => /^[A-Za-z0-9_-]$/.test(char) ? char : `~${char.codePointAt(0)!.toString(16)}~`).join("");
}

/** İncelenemeyen iddiaların nedeni (backend_v2 iddia `status` değeri). Hüküm değildir. */
export const UNFINISHED_REASON: Record<"timeout" | "error" | "skipped", string> = {
  timeout: "süre sınırı içinde incelenemedi",
  error: "incelenirken bir hata oluştu",
  skipped: "metinde çok iddia olduğu için incelenmedi",
};
