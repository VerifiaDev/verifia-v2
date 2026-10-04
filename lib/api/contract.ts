/**
 * Backend (FastAPI) ile arayüz arasındaki HAM sözleşme. Telde giden şekil budur.
 *
 * DURUM: Kısmen teyitli. Yol ve `results` şekli backend'den alındı; gerisi "bizim anlayışımız"dır.
 * Backend değişirse yalnızca bu dosya ve `adapter.ts` güncellenir; arayüze dokunulmaz.
 * Ayrıntılı açıklama: docs/API_CONTRACT.md
 */

/**
 * Servis arayüzüne (service.ts) verilen istek. Gerçek backend'e (POST {BASE}/verify) yalnızca `{ text }` gider;
 * `input_type` telde gitmez, hangi sekmeden gelindiğini servise bildirir (mock bağlantı senaryosu için kullanır).
 */
export interface RawCheckRequest {
  text: string;
  /** "url" ise `text` alanında bağlantı vardır. */
  input_type: "text" | "url";
}

export interface RawEvidence {
  id?: string;
  /** Kısa kanıt pasajı */
  text?: string;
  /** Kaynak adı (örn. "Reuters"); bazı biçimlerde `title` */
  source?: string;
  title?: string;
  url: string;
  /** Arayüz bunu GÖSTERMEZ (adapter okumaz). */
  score?: number;
  /** ISO tarih */
  published_at?: string | null;
}

export interface RawClaim {
  id?: string;
  /** Gerçek backend iddia kimliğini `claim_id` olarak verir. */
  claim_id?: string;
  /** Gerçek backend: açıklamada gerçekten kullanılan kaynak kimlikleri (arayüz şimdilik atıflardan okur). */
  used_sources?: string[];
  /** İddia metni; bazı biçimlerde `text` */
  claim?: string;
  text?: string;
  /** SUPPORTED | REFUTED | CONFLICTING(_EVIDENCE) | NOT ENOUGH EVIDENCE (yazım farkları adapter'da toparlanır) */
  verdict?: string;
  /** İçinde [kaynak_1] gibi atıflar olabilir */
  explanation?: string;
  /** 0 ile 1 arası. Arayüz "modelin güven puanı" olarak gösterir; yoksa hiçbir şey göstermez. */
  confidence?: number;
  evidence?: RawEvidence[];
  /** `evidence` ile aynı anlamda alternatif ad */
  sources?: RawEvidence[];
  /** false ise iddia kontrol edilemez (görüş, tahmin) ve ayrı gösterilir. */
  is_verifiable?: boolean;
}

/** İki biçim de kabul edilir: iddia listesi ya da tek iddia. */
export type RawCheckResponse = { results: RawClaim[] } | { claims: RawClaim[] } | RawClaim;

/** Hata cevabının gövdesi (HTTP 4xx/5xx). */
export interface RawErrorBody {
  error: { code: string; message: string };
}
