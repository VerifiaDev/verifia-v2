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
  | "NETWORK"
  /** Tarayıcı çevrimdışı olduğunu bildiriyor (arayüzün kendi kodu; istek hiç gönderilemedi). */
  | "OFFLINE"
  /** Sunucu sağlık denetimine süresinde yanıt vermedi; inceleme isteği hiç gönderilmedi (arayüzün kendi kodu). */
  | "SERVER_BUSY"
  /** Sunucu istek sınırına takıldık (HTTP 429). */
  | "RATE_LIMITED"
  /** Günlük toplam inceleme sınırı doldu. */
  | "QUOTA_EXCEEDED"
  /** Arama ya da yapay zekâ servisi geçici olarak kullanılamıyor (HTTP 502/503). */
  | "SERVICE_UNAVAILABLE"
  | "INTERNAL_ERROR";

export interface Source {
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

export interface CheckResult {
  claims: Claim[];
  /** Doğrulanamaz bulunan ifadeler (görüş, tahmin vb.) */
  unverifiable: string[];
  /**
   * Sonucu okunamayan iddialar: metni geldi ama sonuç değeri tanınmadı ya da hiç gelmedi.
   * Arayüz bunlar için hüküm göstermez; diğer iddiaların sonucu yine gösterilir (kısmi sonuç).
   */
  unreadable: string[];
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
