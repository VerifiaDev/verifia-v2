/**
 * Arayüzün kendi tipleri. Backend'in ham cevabı burada DEĞİL, lib/adapter.ts içinde
 * karşılanır ve bu tiplere çevrilir. Backend değişirse yalnızca adapter güncellenir.
 */

export type Verdict = "SUPPORTED" | "REFUTED" | "NOT_ENOUGH_EVIDENCE" | "CONFLICTING";

/** İleride: "image" (ekran görüntüsü), "image_text". Şimdilik yalnızca bunlar. */
export type InputMode = "text" | "url";

export type ErrorCode =
  | "INVALID_INPUT"
  | "INPUT_TOO_LONG"
  | "URL_UNREADABLE"
  /** Bağlantı hiç denenmedi: bağlı servis bağlantıyla incelemeyi desteklemiyor (arayüzün kendi kodu). */
  | "URL_UNSUPPORTED"
  | "IMAGE_UNREADABLE"
  | "TIMEOUT"
  | "RATE_LIMITED"
  | "NETWORK"
  /** Tarayıcı çevrimdışı olduğunu bildiriyor (arayüzün kendi kodu; istek hiç gönderilemedi). */
  | "OFFLINE"
  /** Sunucu sağlık denetimine süresinde yanıt vermedi; inceleme isteği hiç gönderilmedi (arayüzün kendi kodu). */
  | "SERVER_BUSY"
  /** Günlük toplam inceleme sınırı doldu. */
  | "QUOTA_EXCEEDED"
  /** Arama ya da yapay zekâ servisi geçici olarak kullanılamıyor (HTTP 502/503). */
  | "SERVICE_UNAVAILABLE"
  | "INTERNAL_ERROR";

export interface Source {
  /** Yalnızca servis veya editör açıkça belirttiğinde gösterilir; sonuçtan türetilmez. */
  relation?: "supports" | "contradicts" | "context";
  excerptKind?: "summary";
  kind?: string;
  /** Açıklamadaki atıfla eşleşen kimlik, örn. "kaynak_1" */
  id: string;
  url: string;
  /** Kaynağın adı (örn. yayın organı). Yoksa arayüz alan adını gösterir. */
  name: string | null;
  /** ISO tarih. Her kaynakta bulunmayabilir. */
  publishedAt: string | null;
  /** Kaynaktan kısa kanıt pasajı */
  excerpt: string | null;
}

export interface Claim {
  id: string;
  text: string;
  verdict: Verdict;
  /** İçinde [kaynak_1] gibi atıflar olabilir */
  explanation: string;
  /** Yalnızca açıklamanın dayandığı kaynaklar */
  sources: Source[];
  /** Modelin kendi güven puanı, 0 ile 1 arasında. Backend vermezse ya da geçersizse null (uydurulmaz). */
  confidence: number | null;
}

/** Backend iddiayı buldu ama sonuç üretemedi (yeni backend: iddia başına `status`). Hüküm gösterilmez. */
export interface UnfinishedClaim {
  text: string;
  reason: "timeout" | "error" | "skipped";
}

export interface CheckResult {
  report?: {
    title?: string;
    summary?: string;
    input?: string;
    preparedAt?: string;
    scope?: string;
  };
  claims: Claim[];
  /** Doğrulanamaz bulunan ifadeler (görüş, tahmin vb.) */
  unverifiable: string[];
  /**
   * Sonucu okunamayan iddialar: metni geldi ama sonuç değeri tanınmadı ya da hiç gelmedi.
   * Arayüz bunlar için hüküm göstermez; diğer iddiaların sonucu yine gösterilir (kısmi sonuç).
   */
  unreadable: string[];
  /** İncelenemeyen iddialar (süre aşımı, hata, çok iddia nedeniyle atlanma). Yoksa boş sayılır. */
  unfinished?: UnfinishedClaim[];
}

/** Backend'in bildirebileceği gerçek işlem aşamaları. Bildirmezse hiçbiri kullanılmaz. */
export type AnalysisStage = "extracting_claims" | "retrieving_evidence" | "verifying";

export interface CheckRequest {
  mode: InputMode;
  content: string;
}

export interface ApiError {
  code: ErrorCode;
  message: string;
}
